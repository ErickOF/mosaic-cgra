"""Directed ownership/error cases and seeded multi-channel workload traffic."""
import random
from itertools import product
from pyuvm import uvm_sequence
from dma_engine.transaction import DmaItem


class DmaSequence(uvm_sequence):
    def __init__(self,c):
        super().__init__('dma_sequence');self.c=c;self.rng=random.Random(c.seed);self.next_id=0;self.last=None

    async def cycle(self,label,ports=None,*,options=None,random=False,edge=True):
        p=dict(i_event_pending=(1<<self.c.NUM_EVENTS)-1);p.update(ports or {})
        item=DmaItem(label,p,options=options,random=random,edge=edge)
        await self.start_item(item);await self.finish_item(item);self.last=item
        return item

    async def reset(self,label='reset'):
        await self.cycle(label,dict(i_rstb=0));await self.cycle('release_reset')

    def command(self,**overrides):
        c=self.c;self.next_id=(self.next_id+1)%(1<<c.COMMAND_ID_WIDTH)
        d=dict(channel=0,mode=0,address_mode=0,source_space=0,destination_space=1 if c.NUM_PROTECTION_REGIONS>1 and c.SPACE_ID_WIDTH>0 else 0,
            source_base=16,destination_base=128,element_size_log2=0,inner_count=min(3,(1<<c.COUNT_WIDTH)-1),outer_count=1,
            source_inner_stride=1,destination_inner_stride=1,source_outer_stride=8,destination_outer_stride=8,
            source_region=0,destination_region=1 if c.NUM_PROTECTION_REGIONS>1 else 0,stream_id=1,context_id=0,id=self.next_id,
            start_mode=0,start_event_mask=1,completion_event_enable=1,completion_event_id=0,stream_last=1,priority=0,
            max_burst_beats=c.MAX_BURST_BEATS)
        d.update(overrides)
        return d

    async def regions(self,context=0):
        for region in range(self.c.NUM_PROTECTION_REGIONS):
            p=dict(i_region_valid=1,i_region_index=region,i_region_enable=1,
                i_region_space_id=region% (1<<self.c.SPACE_ID_WIDTH),i_region_base=0,i_region_limit=1<<self.c.ADDR_WIDTH,
                i_region_context_id=context,i_region_read_enable=1,i_region_write_enable=1)
            for _ in range(100):
                item=await self.cycle('region_setup',p)
                if item.pre.ports['o_region_ready']=='1':break
            else:raise AssertionError('Region setup did not reach quiescence')

    async def region_entry(self,index=0,**overrides):
        d=dict(index=index,enable=1,space_id=index%(1<<self.c.SPACE_ID_WIDTH),base=0,
            limit=1<<self.c.ADDR_WIDTH,context_id=0,read_enable=1,write_enable=1)
        d.update(overrides)
        return await self.cycle('region_entry',{'i_region_'+name:value for name,value in d.items()}|dict(i_region_valid=1))

    async def submit(self,d,*,options=None,events=None,controls=None):
        p={'i_command_'+name:value for name,value in d.items()}
        p['i_command_valid']=1
        if events is not None:p['i_event_pending']=events
        p.update(controls or {})
        for _ in range(2000):
            item=await self.cycle('submit_command',p,options=options)
            if item.pre.ports['o_command_ready']=='1':return item
        raise AssertionError('DMA command acceptance timed out')

    async def drain(self,*,options=None,limit=2000,ports=None):
        for _ in range(limit):
            item=await self.cycle('drain',ports,options=options)
            if item.observation.ports['o_idle']=='1':return item
        raise AssertionError('DMA failed to drain')

    async def cancel(self,d,*,options=None,events=None):
        p=dict(i_cancel_valid=1,i_cancel_channel=d['channel'],i_cancel_context_id=d['context_id'],i_cancel_command_id=d['id'])
        if events is not None:p['i_event_pending']=events
        return await self.cycle('cancel',p,options=options)

    async def transfers(self):
        c=self.c
        for channel,mode in product(range(c.NUM_CHANNELS),range(3)):
            await self.submit(self.command(channel=channel,mode=mode));await self.drain()
        for mode,address,size in product(range(3),range(3),range(c.derived['MAX_ELEMENT_BYTES_LOG2']+1)):
            step=1<<size
            d=self.command(mode=mode,address_mode=address,element_size_log2=size,source_inner_stride=step,
                destination_inner_stride=step,source_outer_stride=step*4,destination_outer_stride=step*4,
                outer_count=min(2,(1<<c.COUNT_WIDTH)-1) if address==2 else 1,
                channel=(mode+address+size)%c.NUM_CHANNELS)
            await self.submit(d);await self.drain()
        for mode,signs in product(range(3),product((-1,0,1),repeat=2)):
            inner,outer=signs
            d=self.command(mode=mode,address_mode=2,source_base=64,destination_base=192,
                source_inner_stride=inner&((1<<c.ADDR_WIDTH)-1),destination_inner_stride=(-inner)&((1<<c.ADDR_WIDTH)-1),
                source_outer_stride=(outer*4)&((1<<c.ADDR_WIDTH)-1),destination_outer_stride=(-outer*4)&((1<<c.ADDR_WIDTH)-1),
                outer_count=min(2,(1<<c.COUNT_WIDTH)-1))
            await self.submit(d);await self.drain()
        # Every channel can be active independently while both global outputs
        # stall. Per-channel queues are filled before releasing the event head.
        if c.SUPPORT_EVENT_START:
            for ch in range(c.NUM_CHANNELS):
                for position in range(c.COMMAND_QUEUE_DEPTH):
                    await self.submit(self.command(channel=ch,mode=position%3,start_mode=2),events=0)
            for _ in range(3):await self.cycle('event_wait',dict(i_event_pending=0))
        else:
            for ch in range(c.NUM_CHANNELS):await self.submit(self.command(channel=ch,mode=ch%3),options=dict(hold_load_data=True,hold_tile_input=True))
        for _ in range(12):await self.cycle('output_backpressure',dict(i_completion_ready=0,i_event_ready=0))
        await self.drain()

    async def invalid_commands(self):
        c=self.c
        bad=[dict(mode=3),dict(address_mode=3),dict(inner_count=0),dict(outer_count=0),dict(max_burst_beats=0),
            dict(source_region=c.NUM_PROTECTION_REGIONS-1,source_space=((c.NUM_PROTECTION_REGIONS-1)+1)%(1<<c.SPACE_ID_WIDTH)),
            dict(context_id=(1<<c.CONTEXT_ID_WIDTH)-1),dict(source_base=(1<<c.ADDR_WIDTH)-1,inner_count=2),
            dict(source_base=0,address_mode=1,source_inner_stride=(1<<c.ADDR_WIDTH)-1,inner_count=2),
            dict(source_base=128,destination_base=128,source_space=0,destination_space=0,destination_region=0)]
        if c.COUNT_WIDTH>1:bad.append(dict(outer_count=2))
        if c.derived['MAX_ELEMENT_BYTES_LOG2']>0:
            bad.extend((dict(element_size_log2=1,source_base=17),dict(address_mode=1,element_size_log2=1,source_inner_stride=1)))
        if not c.SUPPORT_EVENT_START:bad.append(dict(start_mode=1))
        bad.extend((dict(start_mode=3),dict(start_mode=1,start_event_mask=0)))
        for fields in bad:
            await self.cycle('clear_rejection_error',dict(i_error_clear=1))
            await self.submit(self.command(**fields));await self.drain()
        for state,field in product('xz',('mode','address_mode','source_base','inner_count','stream_id','context_id','id','priority')):
            await self.cycle('clear_rejection_error',dict(i_error_clear=1))
            await self.submit(self.command(**{field:state*self.c.widths['i_command_'+field]}));await self.drain()
        # Duplicate IDs are checked while a command remains queued or active.
        d=self.command()
        await self.submit(d,options=dict(hold_store_arm=True))
        await self.submit(d,options=dict(hold_store_arm=True));await self.drain()

    async def protection_and_unknowns(self):
        c=self.c
        for region in range(c.NUM_PROTECTION_REGIONS):
            space=region%(1<<c.SPACE_ID_WIDTH)
            await self.submit(self.command(mode=1,source_region=region,source_space=space));await self.drain()
            await self.region_entry(region,read_enable=0)
            await self.submit(self.command(mode=1,source_region=region,source_space=space));await self.drain()
            await self.region_entry(region,write_enable=0)
            await self.submit(self.command(mode=2,destination_region=region,destination_space=space));await self.drain()
            await self.region_entry(region,enable=0)
            await self.submit(self.command(mode=1,source_region=region,source_space=space));await self.drain()
            await self.region_entry(region)
        for fields in (dict(limit=0),dict(read_enable=0,write_enable=0),dict(base=32,limit=32)):
            item=await self.region_entry(**fields)
            assert item.observation.ports['o_region_rejected']=='1'
        await self.region_entry(base=32,limit=64)
        await self.submit(self.command(mode=1,source_base=31));await self.drain()
        await self.region_entry()
        # Reassignment must fail to handshake while an owner is active.
        await self.submit(self.command(),options=dict(hold_load_data=True))
        for _ in range(4):await self.cycle('region_owner_setup',options=dict(hold_load_data=True))
        item=await self.cycle('region_update_while_busy',dict(i_region_valid=1,i_region_enable=0),options=dict(hold_load_data=True))
        assert item.pre.ports['o_region_ready']=='0'
        await self.drain()
        # Extreme opposite signs have a legal first/final address but an illegal
        # affine rectangle corner; checking endpoints alone would miss this.
        stride=(1<<(c.ADDR_WIDTH-1))-1;negative=(-stride)&((1<<c.ADDR_WIDTH)-1)
        for side in ('source','destination'):
            await self.submit(self.command(address_mode=2,inner_count=2,outer_count=2,
                **{side+'_inner_stride':stride,side+'_outer_stride':negative}));await self.drain()
        for state in 'xz':
            for name in ('i_drain','i_flush','i_error_clear','i_command_valid','i_cancel_valid','i_region_valid',
                    'i_completion_ready','i_event_ready','i_event_pending'):
                await self.cycle('unknown_control',{name:state*c.widths[name]})
                await self.cycle('clear_unknown_control',dict(i_error_clear=1))
            await self.cycle('unknown_channel',dict(i_command_valid=1,i_command_channel=state*c.derived['CHANNEL_WIDTH']))
            await self.cycle('clear_unknown_channel',dict(i_error_clear=1))
            # Ignored fields must be normalized before protected queue storage.
            for mode in (0,1,2):
                d=self.command(mode=mode)
                for side in ('source','destination'):
                    d[side+'_inner_stride']=state*c.ADDR_WIDTH;d[side+'_outer_stride']=state*c.ADDR_WIDTH
                d['start_event_mask']=state*c.NUM_EVENTS
                d['completion_event_enable']=0;d['completion_event_id']=state*c.derived['EVENT_ID_WIDTH']
                if mode==1:
                    for name in ('destination_space','destination_base','destination_region'):
                        d[name]=state*c.widths['i_command_'+name]
                if mode==2:
                    for name in ('source_space','source_base','source_region'):d[name]=state*c.widths['i_command_'+name]
                await self.submit(d);await self.drain()

    async def queue_capacity(self):
        c=self.c;options=dict(hold_load_arm=True,hold_store_arm=True,hold_tile_input=True)
        for ch in range(c.NUM_CHANNELS):
            for _ in range(c.COMMAND_QUEUE_DEPTH+1):await self.submit(self.command(channel=ch),options=options)
        d=self.command();p={'i_command_'+name:value for name,value in d.items()}|dict(i_command_valid=1)
        for _ in range(2):
            item=await self.cycle('full_command_queue',p,options=options)
            assert item.pre.ports['o_command_ready']=='0'
        await self.submit(d);await self.drain()
        n=min((1<<c.COUNT_WIDTH)-1,c.DATA_FIFO_DEPTH+2)
        await self.submit(self.command(inner_count=n),options=dict(hold_store_data=True))
        for _ in range(100):
            item=await self.cycle('fill_internal_fifo',options=dict(hold_store_data=True))
            if int(item.observation.ports['o_data_fifo_occupancy'],2)&((1<<c.derived['DATA_OCCUPANCY_WIDTH'])-1)==c.DATA_FIFO_DEPTH:break
        else:raise AssertionError('Internal FIFO did not fill')
        await self.drain(options=dict(full_rate=True))

    async def event_conditions(self):
        c=self.c
        if not c.SUPPORT_EVENT_START:return
        for mode,population in product((1,2),range(1,c.NUM_EVENTS+1)):
            mask=(1<<population)-1
            d=self.command(start_mode=mode,start_event_mask=mask,channel=population%c.NUM_CHANNELS)
            await self.submit(d,events=0)
            partial=0 if mode==1 else mask>>1
            for _ in range(3):
                item=await self.cycle('blocked_event_drain',dict(i_event_pending=partial,i_drain=1))
                assert int(item.observation.ports['o_event_command_start'],2)==0 and item.observation.ports['o_drain_done']=='0'
            pending=1 if mode==1 else mask
            await self.drain(ports=dict(i_event_pending=pending,i_drain=1))
            assert self.last.observation.ports['o_drain_done']=='1'
            await self.cycle('release_drain')

    async def output_queue_pressure(self):
        c=self.c;blocked=dict(i_completion_ready=0,i_event_ready=0)
        for flush in (False,True):
            for index in range(min(c.COMPLETION_QUEUE_DEPTH,c.EVENT_QUEUE_DEPTH)+2):
                await self.submit(self.command(channel=index%c.NUM_CHANNELS),controls=blocked)
            for _ in range(100):await self.cycle('completion_event_queue_full',blocked)
            assert self.last.observation.ports['o_completion_valid']==self.last.observation.ports['o_event_valid']=='1'
            if flush:
                await self.cycle('flush_held_outputs',blocked|dict(i_flush=1))
                for _ in range(100):
                    item=await self.cycle('flush_output_wait')
                    if item.observation.ports['o_flushed']=='1':break
                else:raise AssertionError('Flush of held outputs failed')
            else:
                for _ in range(3):await self.cycle('completion_only_release',dict(i_completion_ready=1,i_event_ready=0))
                for _ in range(3):await self.cycle('event_only_release',dict(i_completion_ready=0,i_event_ready=1))
            await self.drain()

    async def cancellations(self):
        c=self.c
        if not c.SUPPORT_CANCELLATION:return
        if c.SUPPORT_EVENT_START:
            entries=[self.command(start_mode=1) for _ in range(c.COMMAND_QUEUE_DEPTH)]
            for d in entries:await self.submit(d,events=0)
            await self.cancel(entries[-1],events=0);await self.drain()
        for mode,options in ((0,dict(hold_store_arm=True)),(0,dict(hold_load_arm=True)),
                (0,dict(hold_store_data=True)),(1,dict(hold_tile_output=True)),(2,dict(hold_tile_input=True)),
                (2,dict(hold_store_done=True))):
            d=self.command(mode=mode,inner_count=min(7,(1<<c.COUNT_WIDTH)-1))
            await self.submit(d,options=options)
            for _ in range(12):await self.cycle('cancel_phase',options=options)
            if options.get('hold_store_done'):
                for _ in range(100):
                    item=await self.cycle('wait_full_cancel_commit',options=options)
                    if int(item.ports['i_store_bytes_committed'],2)&((1<<c.derived['BYTE_COUNT_WIDTH'])-1)==d['inner_count']:break
                else:raise AssertionError('Full-commit cancellation setup failed')
            await self.cancel(d,options=options);await self.drain()
        d=self.command(mode=2);options=dict(tile_limit=1)
        await self.submit(d,options=options)
        for _ in range(100):
            item=await self.cycle('partial_commit_cancel',options=options)
            if int(item.ports['i_store_bytes_committed'],2)&((1<<c.derived['BYTE_COUNT_WIDTH'])-1)==1:break
        else:raise AssertionError('Partial cancellation setup failed')
        await self.cancel(d,options=options);await self.drain()
        # A full copy FIFO can still contain data when both peers acknowledge
        # on the final legal cancel edge. Teardown must finish without timeout.
        if (2<=c.CANCEL_TIMEOUT_CYCLES<=c.DATA_FIFO_DEPTH
                and c.DATA_FIFO_DEPTH<(1<<c.COUNT_WIDTH)):
            options=dict(hold_store_data=True,full_rate=True,cancel_delay=c.CANCEL_TIMEOUT_CYCLES-1)
            d=self.command(inner_count=c.DATA_FIFO_DEPTH)
            await self.submit(d,options=options)
            for _ in range(c.DATA_FIFO_DEPTH+20):
                item=await self.cycle('fill_cancel_deadline_fifo',options=options)
                occupancy=int(item.observation.ports['o_data_fifo_occupancy'],2)&((1<<c.derived['DATA_OCCUPANCY_WIDTH'])-1)
                if occupancy==c.DATA_FIFO_DEPTH:break
            else:raise AssertionError('Cancellation deadline FIFO did not fill')
            await self.cancel(d,options=options);await self.drain(options=options)
            assert self.last.observation.ports['o_fatal_error']=='0','Acknowledged cancellation became fatal'
        await self.cancel(self.command())

    async def timeout_flush_reset(self):
        c=self.c
        if c.TRANSFER_TIMEOUT_CYCLES<=256:
            d=self.command();options=dict(hold_store_arm=True)
            await self.submit(d,options=options)
            for _ in range(c.TRANSFER_TIMEOUT_CYCLES+8):await self.cycle('transfer_timeout',options=options)
            await self.drain()
        for phase,options in (('arm',dict(hold_load_arm=True)),('data',dict(hold_store_data=True)),('output',{})):
            for ch in range(c.NUM_CHANNELS):await self.submit(self.command(channel=ch),options=options)
            for _ in range(5):await self.cycle('flush_setup',options=options)
            await self.cycle('flush_'+phase,dict(i_flush=1),options=options)
            for _ in range(500):
                item=await self.cycle('flush_wait')
                if item.observation.ports['o_flushed']=='1':break
            else:raise AssertionError('Coordinated flush did not complete')
            await self.drain()
        for label,options in (('idle',{}),('arm',dict(hold_store_arm=True)),('data',dict(hold_store_data=True))):
            if label!='idle':
                await self.submit(self.command(),options=options)
                for _ in range(5):await self.cycle('reset_setup',options=options)
            await self.reset('reset_'+label);await self.regions()

    async def framing_and_backend_errors(self):
        c=self.c
        for mode in (0,1,2):
            for position in range(3):
                for field in ('first','last','keep'):
                    # All profiles have room for three elements. A wrong first
                    # or final claim is tested at every descriptor position.
                    key='tile_fault' if mode==2 else 'load_fault'
                    actual='descriptor_last' if mode==2 and field=='last' else field
                    value=(int(position!=0) if field=='first' else int(position!=2) if field=='last' else 0)
                    options={key:(actual,position,value)}
                    await self.submit(self.command(mode=mode,inner_count=3),options=options)
                    await self.drain(options=options)
            key='tile_fault' if mode==2 else 'load_fault'
            options={key:('error',1,1)}
            await self.submit(self.command(mode=mode),options=options);await self.drain(options=options)
        for field,value in (('id',2),('context_id',1),('last',0)):
            position=2 if field=='last' else 1
            options=dict(tile_fault=(field,position,value))
            await self.submit(self.command(mode=2),options=options);await self.drain(options=options)
        for backend in ('load','store'):
            options={backend+'_done_error':True}
            await self.submit(self.command(),options=options);await self.drain(options=options)
        # A rejected backend descriptor is fatal, although already armed peers
        # must still cancel safely and the command reports an error completion.
        for backend in ('load','store'):
            options={'hold_'+backend+'_arm':True}
            await self.submit(self.command(),options=options)
            for _ in range(30):
                item=await self.cycle('wait_backend_rejection',options=options)
                if int(item.observation.ports['o_'+backend+'_config_valid'],2)&1:break
            await self.cycle('reject_backend_descriptor',{f'i_{backend}_config_rejected':1},options=options)
            await self.drain()
            assert self.last.observation.ports['o_fatal_error']=='1'
            await self.reset('reset_backend_fatal');await self.regions()

    async def four_state_payloads(self):
        for mode,state in product(range(3),'xz'):
            options=dict(unknown_payload=('tile' if mode==2 else 'load',1,state))
            await self.submit(self.command(mode=mode),options=options)
            await self.drain(options=options)

    async def stale_and_faults(self):
        c=self.c
        options=dict(hold_load_data=True,hold_store_data=True)
        await self.submit(self.command(),options=options)
        for _ in range(15):await self.cycle('stale_setup',options=options)
        epoch=int(self.last.observation.ports['o_descriptor_epoch'],2)
        stale=(epoch-1)% (1<<c.DESCRIPTOR_EPOCH_WIDTH)
        await self.cycle('stale_completions',dict(i_load_done=1,i_store_done=1,
            i_load_done_epoch=stale,i_store_done_epoch=stale,i_store_bytes_committed=123),options=options)
        await self.cycle('stale_data',dict(i_load_stream_valid=1,i_load_stream_epoch=stale,
            i_load_stream_data=0,i_load_stream_keep=1,i_load_stream_first=1),options=options)
        await self.drain()
        if c.check_internals and c.SUPPORT_EVENT_START and c.PROTECT_COMMAND_FIFO:
            await self.reset('reset_before_parity');await self.regions()
            await self.submit(self.command(start_mode=1),events=0)
            await self.cycle('command_parity_fault',dict(i_event_pending=0),options=dict(corrupt_command=(0,0,0)))
            item=await self.cycle('parity_fatal',dict(i_event_pending=0))
            assert item.observation.ports['o_fatal_error']=='1' and int(item.observation.ports['o_load_config_valid'],2)==0
            await self.reset('reset_parity');await self.regions()
        if c.SUPPORT_CANCELLATION and c.CANCEL_TIMEOUT_CYCLES<=64:
            d=self.command(mode=2);options=dict(hold_tile_input=True,hold_cancel_ack=True)
            await self.submit(d,options=options)
            for _ in range(10):await self.cycle('cancel_timeout_setup',options=options)
            await self.cancel(d,options=options)
            for _ in range(c.CANCEL_TIMEOUT_CYCLES+3):await self.cycle('cancel_timeout',options=options)
            assert self.last.observation.ports['o_fatal_error']=='1'
            await self.reset('reset_cancel_timeout');await self.regions()
        # A clear request acknowledges old state, not a new fatal response on
        # the same edge. An idle backend must not complete a nonexistent command.
        await self.drain()
        epoch=int(self.last.observation.ports['o_descriptor_epoch'],2)
        item=await self.cycle('clear_with_new_backend_fault',dict(i_error_clear=1,
            i_load_done=1,i_load_done_epoch=epoch))
        assert item.observation.ports['o_fatal_error']==item.observation.ports['o_error']=='1'
        assert int(item.observation.ports['o_error_code'],2)==15
        await self.cycle('retain_new_fatal_error')
        await self.reset('reset_clear_collision');await self.regions()

    async def maximum_counts(self):
        c=self.c;n=(1<<c.COUNT_WIDTH)-1
        options=dict(hold_store_arm=True)
        await self.submit(self.command(address_mode=2,inner_count=n,outer_count=n,
            source_inner_stride=0,destination_inner_stride=0,source_outer_stride=0,destination_outer_stride=0),options=options)
        for _ in range(3):await self.cycle('maximum_count_prefix',options=options)
        await self.cycle('maximum_count_flush',dict(i_flush=1),options=options)
        for _ in range(100):
            item=await self.cycle('maximum_count_flush_wait')
            if item.observation.ports['o_flushed']=='1':break
        else:raise AssertionError('Maximum-count cancellation did not finish')
        await self.drain()

    async def metadata_extremes(self):
        c=self.c
        contexts=sorted({0,1<<(c.CONTEXT_ID_WIDTH-1),(1<<c.CONTEXT_ID_WIDTH)-1})
        streams=sorted({0,1<<(c.STREAM_ID_WIDTH-1),(1<<c.STREAM_ID_WIDTH)-1})
        for context in contexts:
            await self.regions(context)
            for mode,stream,last in product((1,2),streams,(0,1)):
                await self.submit(self.command(mode=mode,stream_id=stream,stream_last=last,context_id=context));await self.drain()
            for priority,burst in product(sorted({0,1<<(c.PRIORITY_WIDTH-1),(1<<c.PRIORITY_WIDTH)-1}),sorted({1,c.MAX_BURST_BEATS})):
                await self.submit(self.command(priority=priority,max_burst_beats=burst,context_id=context));await self.drain()
        await self.regions()
        for event in range(c.NUM_EVENTS):
            await self.submit(self.command(mode=1,inner_count=1,completion_event_id=event));await self.drain()
        # IDs are unique within a channel, so distinct channels may reuse them.
        for channel in range(c.NUM_CHANNELS):
            await self.submit(self.command(channel=channel,id=(1<<c.COMMAND_ID_WIDTH)-1),
                options=dict(hold_load_data=True))
        await self.drain()

    async def clockless_reset(self):
        for active in (False,True):
            if active:
                await self.submit(self.command(),options=dict(hold_load_data=True))
                for _ in range(4):await self.cycle('clockless_active_setup',options=dict(hold_load_data=True))
            await self.cycle('clockless_reset_assert',dict(i_rstb=0),edge=False)
            await self.cycle('clockless_reset_release',edge=False)
            if self.c.ASYNC_RESET:await self.regions()
            await self.drain()

    async def randomized(self):
        c=self.c;pending=None
        for index in range(c.random_cycles):
            if pending is None and self.rng.random()<0.25:
                mode=self.rng.randrange(3);address=self.rng.randrange(3)
                pending=self.command(channel=self.rng.randrange(c.NUM_CHANNELS),mode=mode,address_mode=address,
                    inner_count=self.rng.randrange(1,min(5,(1<<c.COUNT_WIDTH)-1)+1),
                    outer_count=self.rng.randrange(1,min(3,(1<<c.COUNT_WIDTH)-1)+1) if address==2 else 1,
                    completion_event_enable=self.rng.randrange(2),stream_last=self.rng.randrange(2))
            p=dict(i_completion_ready=int(self.rng.random()<0.8),i_event_ready=int(self.rng.random()<0.8))
            if pending is not None:p.update({'i_command_'+name:value for name,value in pending.items()});p['i_command_valid']=1
            item=await self.cycle(f'random_{index}',p,random=True)
            if pending is not None and item.pre.ports['o_command_ready']=='1':pending=None
        if pending is not None:await self.submit(pending)
        await self.drain()

    async def body(self):
        await self.reset();await self.regions()
        await self.transfers();await self.invalid_commands();await self.protection_and_unknowns()
        await self.queue_capacity();await self.output_queue_pressure();await self.event_conditions();await self.cancellations()
        await self.timeout_flush_reset();await self.framing_and_backend_errors();await self.stale_and_faults()
        await self.four_state_payloads();await self.maximum_counts();await self.metadata_extremes();await self.clockless_reset();await self.randomized()
        await self.cycle('final_idle')
