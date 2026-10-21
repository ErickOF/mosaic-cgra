"""Descriptor-driven directed, exhaustive, workload and seeded-random traffic."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from agu.model import Mode
from agu.transaction import AguItem, DESCRIPTOR


class AguSequence(uvm_sequence):
    def __init__(self,config):
        super().__init__('agu_sequence')
        self.c = config
        self.rng = random.Random(config.seed)
        self.empty = dict(i_mode=0,i_base_address=0,i_inner_count=1,i_outer_count=1,
            i_inner_stride=0,i_outer_stride=0,i_element_size_log2=0,i_is_write=0,
            i_address_space=0,i_channel_id=0,i_context_id=0,i_emit_end_of_stream=0)

    async def cycle(self,label,*,descriptor=None,valid=0,ready=1,clear=0,rstb=1,
            edge=True,random=False,**overrides):
        c = self.c
        # Invalid descriptors deliberately contain X fields. This verifies the
        # idle cone and active captured metadata are independent of live ports.
        p = ({name:'x'*c.widths[name] for name in DESCRIPTOR} if descriptor is None
            else self.empty | descriptor)
        p.update(i_rstb=rstb,i_error_clear=clear,i_config_valid=valid,i_ready=ready)
        p.update(overrides)
        item = AguItem(label,{name:bits(value,c.widths[name]) for name,value in p.items()},edge=edge,random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self,**kwargs):
        return await self.cycle('reset',rstb=0,**kwargs)

    async def run_descriptor(self,descriptor,*,pattern=(1,),label='descriptor',limit=1024):
        await self.cycle('clear_before_'+label,clear=1)
        item = await self.cycle(label,descriptor=descriptor,valid=1,ready=pattern[0])
        for index in range(limit):
            p = item.observation.ports
            if p['o_valid']!='1': break
            item = await self.cycle('drain_'+label,ready=pattern[index % len(pattern)])
        else:
            await self.reset()  # Deliberately bounded maximum-count descriptors.
        await self.cycle('quiet_after_'+label)
        return item

    async def modes_and_metadata(self):
        c = self.c
        n = min(3,c.count_max)
        for mode,inner,outer in product(Mode,sorted({1,min(2,c.count_max),n}),sorted({1,n})):
            if mode!=Mode.TWO_D and outer!=1: continue
            await self.run_descriptor(dict(i_mode=int(mode),i_inner_count=inner,i_outer_count=outer),label='count_classes')
        for mode,size,inner_sign,outer_sign in product(Mode,range(c.max_log2+1),(-1,0,1),(-1,0,1)):
            step = 1 << size
            # Small addresses may fail the successor range check; the descriptor
            # itself is always aligned and legal. Midpoint supports +/- strides.
            base = ((c.mask//2)//step)*step
            await self.run_descriptor(dict(i_mode=int(mode),i_base_address=base,i_inner_count=n,
                i_outer_count=n if mode==Mode.TWO_D else 1,i_element_size_log2=size,
                i_inner_stride=(inner_sign*step)&c.mask,i_outer_stride=(outer_sign*step)&c.mask,
                i_emit_end_of_stream=1),label='mode_sign_size')
        for direction,space,channel,context,eos in product((0,1),(0,(1<<c.space)-1),
                (0,(1<<c.channel)-1),(0,(1<<c.context)-1),(0,1)):
            await self.run_descriptor(dict(i_mode=2,i_inner_count=n,i_outer_count=n,
                i_is_write=direction,i_address_space=space,i_channel_id=channel,
                i_context_id=context,i_emit_end_of_stream=eos),label='metadata',pattern=(0,1,1))
        # Streaming, matrix row, column, convolution-window and repeated-address
        # shapes. All use small counts; the reference also checks early range exit.
        for mode,inner,outer in ((0,0,0),(1,2,0),(1,-1,0),(2,1,5),(2,4,1),(2,0,-2),(2,-1,4)):
            await self.run_descriptor(dict(i_mode=mode,i_base_address=c.mask//2,
                i_inner_count=min(5,c.count_max),i_outer_count=min(3,c.count_max) if mode==2 else 1,
                i_inner_stride=inner&c.mask,i_outer_stride=outer&c.mask),label='workload',pattern=(1,1,1,0))

    async def errors_and_unknowns(self):
        c = self.c
        descriptors = [dict(i_mode=3),dict(i_inner_count=0),dict(i_outer_count=0)]
        if c.count_max>1: descriptors.append(dict(i_outer_count=2))
        if c.max_log2 < (1<<c.size_width)-1:
            descriptors.append(dict(i_element_size_log2=c.max_log2+1))
        if c.max_log2:
            descriptors.append(dict(i_element_size_log2=1,i_base_address=1))
            for value in (1,-1):
                descriptors.extend((dict(i_mode=1,i_element_size_log2=1,i_inner_stride=value&c.mask),
                    dict(i_mode=2,i_element_size_log2=1,i_outer_stride=value&c.mask)))
        for descriptor in descriptors:
            await self.run_descriptor(descriptor,label='illegal')
            for _ in range(3):
                await self.cycle('sticky_error',descriptor=self.empty,valid=1)
            await self.cycle('recover_error',clear=1,descriptor=self.empty,valid=1)
            await self.run_descriptor({},label='restart_after_error')
        for state,mode in product('xz',Mode):
            for name in DESCRIPTOR:
                d = dict(i_mode=int(mode),**{name:state*c.widths[name]}) if name!='i_mode' else {name:state*2}
                await self.run_descriptor(d,label='unknown_descriptor')
            ignored = {'i_inner_stride','i_outer_stride'} if mode==Mode.LINEAR else {'i_outer_stride'} if mode==Mode.STRIDED else set()
            if ignored:
                await self.run_descriptor(dict(i_mode=int(mode),**{name:state*c.widths[name] for name in ignored}),label='ignored_strides')
            await self.cycle('ignored_invalid_descriptor',**{name:state*c.widths[name] for name in DESCRIPTOR})
        # Unknown ready is an explicit hold, never an optimistic handshake.
        await self.cycle('clear_unknown_ready',clear=1)
        await self.cycle('start_unknown_ready',descriptor=dict(i_mode=1,i_inner_count=min(3,c.count_max)),valid=1)
        for ready in ('x','z',0,1): await self.cycle('ready_four_state',ready=ready)
        await self.reset()

    async def range_positions(self):
        c = self.c
        for negative,position,mode in product((False,True),range(min(6,c.count_max-1)),(1,2)):
            if c.width==1 and not negative and mode==2: continue
            # Within-row range failure and next-row range failure, including
            # one-element rows. The final accepted address must never be checked
            # against an unused successor.
            base = position if negative else c.mask-position
            step = (-1 if negative else 1)&c.mask
            await self.run_descriptor(dict(i_mode=0 if c.width==1 and not negative else mode,i_base_address=base,
                i_inner_count=position+2 if mode==1 else 1,i_outer_count=position+2 if mode==2 else 1,
                i_inner_stride=step,i_outer_stride=step),label='range_position',pattern=(0,1,1))
        for base,step in ((0,-1),(c.mask,1)):
            await self.run_descriptor(dict(i_mode=1,i_base_address=base,i_inner_stride=step&c.mask),label='final_no_successor')

    async def alignment_and_extremes(self):
        c=self.c
        for size in range(1,c.max_log2+1):
            await self.run_descriptor(dict(i_mode=2,i_element_size_log2=size),label='aligned_size')
            await self.run_descriptor(dict(i_element_size_log2=size,i_base_address=(1<<size)-1),label='misaligned_size_base')
            for negative in (False,True):
                step=(-1 if negative else 1)&c.mask
                await self.run_descriptor(dict(i_mode=1,i_element_size_log2=size,i_inner_stride=step),label='misaligned_size_inner')
                await self.run_descriptor(dict(i_mode=2,i_element_size_log2=size,i_outer_stride=step),label='misaligned_size_outer')
        extremes=(-(1<<(c.width-1)),(1<<(c.width-1))-1)
        for mode,inner,outer,base in product((1,2),extremes,extremes,(0,c.mask,c.mask//2)):
            await self.run_descriptor(dict(i_mode=mode,i_inner_count=min(3,c.count_max),
                i_outer_count=min(3,c.count_max) if mode==2 else 1,i_base_address=base,
                i_inner_stride=inner&c.mask,i_outer_stride=outer&c.mask),label='full_width_stride',pattern=(1,0,1))

    async def stalls_resets_counts(self):
        c = self.c
        n=min(3,c.count_max)
        for inner,outer in product(sorted({1,n}),repeat=2):
            await self.run_descriptor(dict(i_mode=2,i_inner_count=inner,i_outer_count=outer,
                i_emit_end_of_stream=1),label='every_marker_long_stall',pattern=(*([0]*32),1))
        for mode,length in product(Mode,(0,1,2,4,32)):
            await self.cycle('clear_stall',clear=1)
            await self.cycle('start_stall',descriptor=dict(i_mode=int(mode),i_inner_count=min(3,c.count_max),
                i_outer_count=min(3,c.count_max) if mode==Mode.TWO_D else 1,
                i_emit_end_of_stream=1),valid=1)
            for _ in range(length):
                await self.cycle('stalled_descriptor',ready=0,clear=1)
            # A producer's descriptor remains stable while waiting. It must not
            # replace the active owner, including on final-address acceptance.
            waiting = self.empty | dict(i_context_id=(1<<c.context)-1)
            for _ in range(1 if c.count_max==1 else 3):
                await self.cycle('waiting_descriptor',descriptor=waiting,valid=1,ready=1)
            await self.reset()
        for state in ('idle','active','stalled','error'):
            for clockless in (False,True):
                await self.reset()
                if state=='error': await self.cycle('prepare_error',descriptor=dict(i_mode=3),valid=1)
                elif state!='idle': await self.cycle('prepare_active',descriptor=dict(i_mode=1,i_inner_count=c.count_max),valid=1)
                if state=='stalled': await self.cycle('prepare_stall',ready=0)
                await self.cycle('reset_'+state,rstb=0,ready=0,edge=not clockless)
                await self.cycle('release_'+state,ready=0,edge=not clockless)
                await self.reset()
                await self.run_descriptor({},label='restart_after_reset')
        for mode in Mode:
            await self.run_descriptor(dict(i_mode=int(mode),i_inner_count=c.count_max,
                i_outer_count=c.count_max if mode==Mode.TWO_D else 1),label='maximum_count',limit=16)
        # Count a complete multi-row product, including upper accepted-count bits.
        if c.count<=4:
            await self.run_descriptor(dict(i_mode=2,i_inner_count=c.count_max,i_outer_count=c.count_max),label='maximum_product')
        else:
            await self.run_descriptor(dict(i_mode=1,i_inner_count=min(64,c.count_max)),label='full_rate',limit=64)

    async def exhaustive(self):
        c = self.c
        if (c.width,c.count,c.max_element)!=(3,2,2): return
        # Every binary legal descriptor in this tractable geometry, crossed with
        # both full-rate and alternating ready. Metadata is crossed separately.
        for mode in Mode:
            inners = range(1<<c.width) if mode!=Mode.LINEAR else (0,)
            outers = range(1<<c.width) if mode==Mode.TWO_D else (0,)
            rows = range(1,c.count_max+1) if mode==Mode.TWO_D else (1,)
            for base,n,rows_count,inner,outer,size in product(range(1<<c.width),range(1,c.count_max+1),
                    rows,inners,outers,range(c.max_log2+1)):
                alignment=1<<size
                if base%alignment or (mode!=Mode.LINEAR and inner%alignment) or (mode==Mode.TWO_D and outer%alignment): continue
                for pattern in ((1,),(0,1)):
                    await self.run_descriptor(dict(i_mode=int(mode),i_base_address=base,i_inner_count=n,
                        i_outer_count=rows_count,i_inner_stride=inner,i_outer_stride=outer,
                        i_element_size_log2=size),label='exhaustive',pattern=pattern)

    async def randomized(self):
        c,rng = self.c,self.rng
        remaining = 0
        ready = 1
        for index in range(c.random_cycles):
            if remaining==0:
                ready = rng.randrange(2)
                remaining = rng.randrange(1,12)
            remaining-=1
            # Descriptors stay stable from proposal until accepted; some attempts
            # intentionally fail legality, then exercise sticky-error recovery.
            if not hasattr(self,'pending') or self.pending is None:
                mode = rng.randrange(4)
                size = rng.randrange(c.max_log2+1)
                align=1<<size
                self.pending = self.empty | dict(i_mode=mode,i_base_address=(rng.getrandbits(c.width)//align)*align,
                    i_inner_count=rng.randrange(1,min(c.count_max,7)+1),
                    i_outer_count=rng.randrange(1,min(c.count_max,5)+1) if mode==2 else 1,
                    i_element_size_log2=size, i_inner_stride=(rng.randrange(-4,5)*align)&c.mask,
                    i_outer_stride=(rng.randrange(-4,5)*align)&c.mask,
                    i_is_write=rng.randrange(2),i_emit_end_of_stream=rng.randrange(2),
                    i_address_space=rng.getrandbits(c.space),i_channel_id=rng.getrandbits(c.channel),i_context_id=rng.getrandbits(c.context))
            item = await self.cycle(f'random_{index}',descriptor=self.pending,valid=1,ready=ready,
                clear=int(rng.randrange(12)==0),rstb=int(rng.randrange(160)!=0),random=True)
            if item.pre.ports['o_config_ready']=='1' or item.ports['i_rstb']=='0': self.pending=None
        await self.reset()

    async def body(self):
        await self.reset()
        await self.modes_and_metadata()
        await self.errors_and_unknowns()
        await self.range_positions()
        await self.alignment_and_extremes()
        await self.stalls_resets_counts()
        await self.exhaustive()
        await self.randomized()
        await self.cycle('final_idle')
