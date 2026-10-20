"""Masked storage, exact latency, credit pressure, cancellation and legal random traffic."""
from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from sram_wrapper.config import LONG_STALL,STREAM_LENGTH
from sram_wrapper.model import known
from sram_wrapper.transaction import SramItem,INPUTS,FIELDS


class SramSequence(uvm_sequence):
    def __init__(self,config):
        super().__init__('sram_wrapper_sequence')
        self.config=config;self.rng=random.Random(config.seed)
        self.ports={name:'0'*config.widths[name] for name in INPUTS}
        self.pending=None;self.last=None;self.serial=0

    async def send(self,label,*,edge=True,random=False,fault_data=False,fault_tag=False,pulse=False,**changes):
        for name,value in changes.items():self.ports[name]=bits(value,self.config.widths[name])
        item=SramItem(label,self.ports,edge=edge,random=random,fault_data=fault_data,fault_tag=fault_tag,pulse=pulse)
        await self.start_item(item);await self.finish_item(item)
        self.last=item.observation.ports
        if self.ports['i_rstb']=='0' or self.ports['i_flush']=='1':self.pending=None
        elif self.ports['i_req_valid']=='1':
            if edge and item.pre.ports['o_req_ready']=='1':self.pending=None
            elif item.pre.ports['o_req_ready']=='0' and item.pre.ports['o_req_error']=='0':
                self.pending=({name:self.ports[name] for name in FIELDS},fault_data,fault_tag)
        return item

    async def idle(self,ready=1,*,edge=True):
        if self.pending:
            fields,fd,ft=self.pending
            return await self.send('pending_request',edge=edge,i_req_valid=1,i_rsp_ready=ready,fault_data=fd,fault_tag=ft,**fields)
        return await self.send('idle',edge=edge,i_req_valid=0,i_rsp_ready=ready)

    async def request(self,write,target=0,word=0,mask=None,tag=None,*,ready=1,fault_data=False,fault_tag=False,label='request'):
        c=self.config;self.serial+=1
        mask=(1<<c.mask_width)-1 if mask is None else mask
        tag=self.serial% (1<<c.tag_width) if tag is None else tag
        item=await self.send(label,i_rstb=1,i_flush=0,i_req_valid=1,i_req_write=int(write),i_req_addr=target,
            i_req_wdata=word,i_req_wmask=mask,i_req_tag=tag,i_rsp_ready=ready,fault_data=fault_data,fault_tag=fault_tag)
        for _ in range(2*c.credits+c.latency+4):
            if item.pre.ports['o_req_ready']=='1':return item
            assert ready,'A deliberately backpressured request must be held explicitly'
            item=await self.idle(ready)
        raise AssertionError('Request did not regain a read credit')

    async def drain(self):
        c=self.config
        for _ in range(2*c.credits+c.latency+4):
            if self.pending is None and self.last and self.last['o_busy']=='0':
                await self.idle(1);return
            await self.idle(1)
        raise AssertionError('Read responses did not drain')

    async def boundary(self,kind):
        c=self.config
        await self.send(kind,i_rstb=int(kind!='reset'),i_flush=int(kind=='flush'),i_req_valid=1,
            i_req_write=1,i_req_addr=0,i_req_wdata=(1<<c.width)-1,i_req_wmask=(1<<c.mask_width)-1,i_req_tag=0,i_rsp_ready=1)
        await self.send('boundary_release',edge=False,i_rstb=1,i_flush=0,i_req_valid=0,i_rsp_ready=0)
        for _ in range(c.latency+2):await self.idle(0)

    async def initialize(self):
        c=self.config
        await self.boundary('reset')
        for target in (range(c.depth) if c.depth<=33 else (0,c.depth//2,c.depth-1)):
            await self.request(False,target)
        await self.drain()
        for target in range(c.depth):await self.request(True,target,self.rng.getrandbits(c.width))
        for target in range(c.depth):await self.request(False,target)
        await self.drain()

    async def masks_and_hazards(self):
        c=self.config;full=(1<<c.mask_width)-1;maximum=(1<<c.width)-1
        masks={0,full,*[1<<i for i in range(c.mask_width)],*[full^(1<<i) for i in range(c.mask_width)],
            sum(1<<i for i in range(0,c.mask_width,2)),sum(1<<i for i in range(1,c.mask_width,2))}
        for mask in sorted(masks):
            for baseline in (0,maximum):
                await self.request(True,0,baseline)
                for word in (maximum^baseline,maximum^baseline,baseline):
                    await self.request(True,0,word,mask)
                    await self.request(False,0)
                await self.drain()
        for target in sorted({0,c.depth//2,c.depth-1}):
            for previous,following in product((False,True),repeat=2):
                await self.drain()
                await self.request(previous,target,self.rng.getrandbits(c.width))
                await self.request(following,target,self.rng.getrandbits(c.width))
        for _ in range(STREAM_LENGTH):await self.request(True,0,self.rng.getrandbits(c.width))
        await self.drain()
        for _ in range(STREAM_LENGTH*2):await self.request(False,self.rng.randrange(c.depth))
        await self.drain()
        for target in range(c.depth,1<<c.address_width):
            for write in (False,True):
                await self.send('invalid_address',i_req_valid=1,i_req_write=int(write),i_req_addr=target,
                    i_req_wdata=maximum,i_req_wmask=full,i_req_tag=0,i_rsp_ready=1)
        await self.idle()

    def tags(self):
        c=self.config;full=(1<<c.tag_width)-1
        return {0,full,*[1<<i for i in range(c.tag_width)],*[full^(1<<i) for i in range(c.tag_width)],
            sum(1<<i for i in range(0,c.tag_width,2)),sum(1<<i for i in range(1,c.tag_width,2))}

    async def pressure(self):
        c=self.config
        for tag in sorted(self.tags()):
            await self.drain()
            for _ in range(c.credits):await self.request(False,0,tag=tag,ready=0)
            for _ in range(c.latency+2):await self.idle(0)
            for _ in range(4):await self.request(True,0,self.rng.getrandbits(c.width),ready=0)
            await self.request(True,0,0,mask=0,ready=0)
            await self.request(True,0,self.rng.getrandbits(c.width),ready=1)
            await self.request(True,0,self.rng.getrandbits(c.width),ready=0)
            await self.request(False,0,tag=tag,ready=0)
            for _ in range(c.latency+2):await self.idle(0)
            # A real stalled read keeps every field stable. Consuming the head
            # must allow that read on the same edge, even at the credit limit.
            await self.send('full_read_backpressure',i_req_valid=1,i_req_write=0,i_req_addr=0,
                i_req_wdata=0,i_req_wmask=0,i_req_tag=tag,i_rsp_ready=0)
            for _ in range(LONG_STALL):await self.idle(0)
            await self.idle(1)
            # Writes and response consumption may also coincide.
            await self.request(True,0,self.rng.getrandbits(c.width),ready=1)
            await self.drain()
        for count in range(1,c.credits+1):
            await self.drain()
            for _ in range(count):await self.request(False,0,ready=0)
            for _ in range(c.latency+LONG_STALL+2):await self.idle(0)
            await self.drain()
        for length in (*range(9),LONG_STALL):
            await self.drain();await self.request(False,0)
            for _ in range(c.latency):await self.idle(1)
            for _ in range(length):await self.idle(0)
            await self.idle(1)

    async def cancellation(self):
        c=self.config
        for kind,stage in product(('reset','flush'),range(c.latency+1)):
            await self.drain();await self.request(False,0,ready=0)
            for _ in range(stage):await self.idle(0)
            await self.boundary(kind)
            await self.request(False,0);await self.drain()
        for kind,count in product(('reset','flush'),range(c.credits+1)):
            await self.drain()
            for _ in range(count):await self.request(False,0,ready=0)
            for _ in range(c.latency+2):await self.idle(0)
            await self.boundary(kind)
        for kind,state in product(('reset','flush'),('empty','inflight','queued')):
            await self.drain()
            if state!='empty':await self.request(False,0,ready=0)
            if state=='queued':
                for _ in range(c.latency+2):await self.idle(0)
            await self.send('unclocked_boundary',edge=False,**{'i_rstb' if kind=='reset' else 'i_flush':0 if kind=='reset' else 1})
            await self.send('unclocked_release',edge=False,i_rstb=1,i_flush=0,i_req_valid=0)
            await self.drain()

    async def data_and_ignored(self):
        c=self.config;maximum=(1<<c.width)-1
        patterns={0,maximum,*[1<<i for i in range(c.width)],*[maximum^(1<<i) for i in range(c.width)]}
        for word in sorted(patterns):
            await self.request(True,0,word);await self.request(False,0)
        await self.drain()
        for state in 'xz':
            await self.send('inactive_unknown_fields',i_req_valid=0,i_req_write=state,i_req_addr=state*c.address_width,
                i_req_wdata=state*c.width,i_req_wmask=state*c.mask_width,i_req_tag=state*c.tag_width)
            await self.request(True,0,state*c.width,mask=0,tag=state*c.tag_width)
            await self.request(False,0,word=state*c.width,mask=state*c.mask_width)
            await self.drain()
            await self.request(True,0,state*c.width,fault_data=True)
            await self.request(False,0,tag=state*c.tag_width,fault_tag=True)
            await self.drain()
        await self.request(True,0,0)

    async def probe(self):
        c=self.config
        await self.boundary('reset')
        name,state,bit=c.probe.split(':')
        if name.startswith('requester_'):
            for _ in range(c.credits):await self.request(False,0,ready=0)
            await self.send('stalled_offer',i_req_valid=1,i_req_write=0,i_req_addr=0,i_req_wdata=0,i_req_wmask=0,i_req_tag=0,i_rsp_ready=0)
            if name=='requester_pulse':await self.send('illegal_pulse',edge=False,pulse=True)
            else:await self.send('illegal_offer',edge=False,**({'i_req_valid':0} if name=='requester_valid' else {name.removeprefix('requester_'):1}))
        else:
            changes=dict(i_req_valid=1,i_req_write=1,i_req_addr=0,i_req_wdata=0,i_req_wmask=(1<<c.mask_width)-1,i_req_tag=0,i_rsp_ready=0)
            target='i_req_wdata' if name=='enabled_write_data' else 'i_req_tag' if name=='read_tag' else name
            if name=='read_tag':changes['i_req_write']=0
            word=list(bits(changes.get(target,1 if target=='i_rstb' else 0),c.widths[target]));word[-int(bit)-1]=state
            changes[target]=''.join(word)
            await self.send('illegal_control',**changes)
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:await self.probe();return
        await self.initialize();await self.masks_and_hazards();await self.pressure();await self.cancellation();await self.data_and_ignored()
        c=self.config
        for index in range(c.random_cycles):
            fields=dict(i_req_write=self.rng.randrange(2),i_req_addr=self.rng.randrange(c.depth),
                i_req_wdata=self.rng.getrandbits(c.width),i_req_wmask=self.rng.getrandbits(c.mask_width),i_req_tag=self.rng.getrandbits(c.tag_width))
            valid=self.rng.randrange(2);fd=ft=False
            if self.pending:fields,fd,ft=self.pending;valid=1
            await self.send(f'random_{index}',random=True,i_rstb=int(self.rng.random()>=0.02),i_flush=int(self.rng.random()<0.02),
                i_req_valid=valid,i_rsp_ready=self.rng.randrange(2),fault_data=fd,fault_tag=ft,**fields)
        await self.drain()
        for target in range(c.depth):await self.request(False,target)
        await self.drain()
