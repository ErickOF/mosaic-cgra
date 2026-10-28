"""Directed protocol/lifecycle tests and reproducible concurrent traffic."""
from collections import defaultdict
import random
from pyuvm import uvm_sequence
from global_noc.transaction import NocItem, INPUTS
from global_noc.model import image, FIELD_WIDTHS
from global_noc_contract import (flow_words, metadata, crc32c, CFG_WRITE, CFG_READ,
    CFG_VALIDATE, CFG_PREPARE, CFG_COMMIT, CFG_ABORT, OK, BAD_CRC, BAD_IMAGE, OWNERSHIP)

class NocSequence(uvm_sequence):
    def __init__(self,c):
        super().__init__('global_noc_sequence')
        self.c=c;self.p=c.parameters;self.a=c.a
        self.rng=random.Random(c.seed)
        self.ports={n:0 for n in INPUTS}
        self.ports.update(i_noc_rstb=1,i_cfg_response_ready=1,i_lifecycle_ready=1,
            i_tile_rx_ready=(1<<(self.a['NE']*self.a['RX']))-1,
            i_response_reserved=(1<<(self.a['NE']*self.a['TX']))-1)
        self.sequence=defaultdict(int);self.serial=0;self.epoch=0;self.version=0
        self.last=None

    async def step(self,**changes):
        self.ports.update(changes)
        item=NocItem(self.ports)
        await self.start_item(item)
        await self.finish_item(item)
        self.last=item
        return item

    async def wait(self,cycles,**changes):
        for _ in range(cycles):await self.step(**changes)

    async def cfg(self,command,*,index=0,data=0,crc=None,status=OK,hold=False,**changes):
        controls=dict(i_cfg_valid=1,i_cfg_command=command,i_cfg_word_index=index,
            i_cfg_write_data=data,i_cfg_write_strobe=255,i_cfg_expected_crc=crc or 0,
            i_cfg_owner_id=1,i_cfg_kernel_id=1,i_cfg_package_id=1,
            i_cfg_expected_version=self.version,i_cfg_tag=self.serial&65535,
            i_cfg_response_ready=0 if hold else 1)
        await self.step(**(controls|changes))
        self.serial+=1
        for _ in range(100):
            if self.last.pre['o_cfg_ready']:break
            await self.step()
        else:raise AssertionError('Configuration request stalled')
        await self.step(i_cfg_valid=0)
        for _ in range(100):
            if self.last.pre['o_cfg_response_valid']:break
            await self.step()
        else:raise AssertionError('Configuration response missing')
        response=self.last.pre
        assert response['o_cfg_response_status']==status,(command,status,response)
        if hold:
            record=tuple(response[n] for n in ('o_cfg_response_data','o_cfg_response_tag',
                'o_cfg_response_status','o_cfg_response_version','o_cfg_response_crc'))
            for _ in range(3):
                item=await self.step()
                assert record==tuple(item.pre[n] for n in ('o_cfg_response_data','o_cfg_response_tag',
                    'o_cfg_response_status','o_cfg_response_version','o_cfg_response_crc'))
            await self.step(i_cfg_response_ready=1)
            self.coverage.hit('held_response')
        self.version=response['o_cfg_response_version']
        return response

    async def load(self,flows,*,faults=None):
        await self.idle()
        await self.step(i_run=0,i_tile_tx_valid=0)
        await self.cfg(CFG_ABORT)
        words=image(self.p,flows,faults)
        for index,word in enumerate(words):await self.cfg(CFG_WRITE,index=index,data=word)
        crc=crc32c(words)
        await self.cfg(CFG_VALIDATE,crc=crc)
        await self.cfg(CFG_PREPARE,crc=crc)
        await self.cfg(CFG_COMMIT,crc=crc)
        self.flows=flows
        self.sequence.clear()
        self.epoch=self.last.post['o_execution_epoch']
        self.coverage.hit('configuration')
        assert not self.last.post['o_running'],'Commit started traffic'
        self.coverage.hit('inactive_start')
        await self.step(i_run=1)

    def beat(self,flow,tc=None,**changes):
        w0,_,w2,w3=flow
        classes=w2>>32&255
        tc=tc if tc is not None else next(c for c in range(8) if classes>>c&1)
        vc=self.p['TRAFFIC_CLASS_TO_VC']>>(tc*self.a['VW'])&((1<<self.a['VW'])-1)
        fid=w0>>1&65535
        seq=self.sequence[fid,vc]+(w3>>16&65535)
        keep=self.rng.randrange(1,1<<self.a['TB'])
        raw=self.rng.getrandbits(self.a['TD'])
        data=sum(((raw>>(b*8)&255) if keep>>b&1 else 0)<<(b*8) for b in range(self.a['TB']))
        self.serial+=1
        beat=dict(data=data,keep=keep,last=self.serial&1,context_id=w0>>49&255,
            message_type=self.rng.randrange(16),traffic_class=tc,packet_id=self.serial&65535,
            user_metadata=metadata(flow,seq,self.epoch),error=self.rng.randrange(256),
            destination_node=w2>>16&255,destination_endpoint=w2>>24&255)
        return beat|changes

    def offers(self,entries):
        values={n:0 for n in self.ports if n.startswith('i_tile_tx_')}
        for index,beat in entries.items():
            values['i_tile_tx_valid'] |= 1<<index
            for name,value in beat.items():
                width=FIELD_WIDTHS[name]
                w=int(width) if width.isdigit() else self.a[width]
                values['i_tile_tx_'+name] |= value<<(index*w)
        return values

    def advance(self,beat):
        vc=self.p['TRAFFIC_CLASS_TO_VC']>>(beat['traffic_class']*self.a['VW'])&((1<<self.a['VW'])-1)
        self.sequence[beat['user_metadata']&65535,vc]+=1

    async def send(self,flow,tc=None,**changes):
        index=(flow[2]&255)*self.a['TX']+(flow[2]>>8&255)
        beat=self.beat(flow,tc,**changes)
        for _ in range(3000):
            item=await self.step(**self.offers({index:beat}))
            if item.pre['o_tile_tx_ready']>>index&1:
                self.advance(beat)
                await self.step(i_tile_tx_valid=0)
                return beat
        raise AssertionError(('Injection watchdog',flow,self.last.post))

    async def reject(self,flow,**changes):
        index=(flow[2]&255)*self.a['TX']+(flow[2]>>8&255)
        beat=self.beat(flow,**changes)
        for _ in range(5):
            item=await self.step(**self.offers({index:beat}))
            assert not item.pre['o_tile_tx_ready']>>index&1,('Illegal injection accepted',beat)
        await self.step(i_tile_tx_valid=0)

    async def idle(self):
        for _ in range(4000):
            item=await self.step(i_tile_tx_valid=0)
            if item.post['o_idle']:
                await self.wait(3)
                return
        raise AssertionError(('Network watchdog',self.last.post))

    async def lifecycle(self,kind,*,mask=0,all_flows=0,status=0):
        await self.step(**{f'i_{kind}_valid':1,f'i_{kind}_tag':0xA35},
            i_drain_all=all_flows,i_drain_flow_mask=mask)
        for _ in range(10):
            if self.last.pre[f'o_{kind}_ready']:break
            await self.step()
        else:raise AssertionError('Lifecycle request stalled')
        await self.step(**{f'i_{kind}_valid':0})
        for _ in range(4000):
            if self.last.pre['o_lifecycle_valid']:
                assert self.last.pre['o_lifecycle_tag']==0xA35
                assert self.last.pre['o_lifecycle_status']==status,self.last.pre
                return
            await self.step()
        raise AssertionError('Lifecycle watchdog')

    async def body(self):
        await self.wait(3,i_noc_rstb=0)
        await self.wait(3,i_noc_rstb=1)
        n=self.a['NE'];rx=self.a['RX'];tx=self.a['TX']
        classes=[0,1,6,7] if self.p['NOC_PROFILE']==0 else list(range(8))
        flows=[]
        for tc in classes:
            src,dst=(n-1,0) if tc==3 else (0,n-1)
            flows.append(flow_words(flow_id=101+tc,source=src,destination=dst,
                tx=tx-1 if tc in (4,5) else 0,
                rx=rx-1 if tc in (4,5) else 0,classes=1<<tc,context=tc+1,
                kernel=2 if tc in (6,7) else 1,reply=104 if tc==2 else 0))
        print('Global NoC: configure and directed traffic',flush=True)
        await self.load(flows)
        words=image(self.p,flows)
        await self.cfg(CFG_READ,index=0,hold=True)
        await self.cfg(CFG_VALIDATE,crc=crc32c(words)^1,status=BAD_CRC)
        self.coverage.hit('crc_rejection')
        await self.cfg(CFG_READ,index=0,status=OWNERSHIP,i_cfg_owner_id=9)
        self.coverage.hit('ownership')
        # Malicious binding fields and stale/duplicate sequences never create a packet.
        f=flows[0]
        await self.reject(f,user_metadata=metadata(f,0,self.epoch)^1)
        await self.reject(f,user_metadata=metadata(f,0,self.epoch)^(1<<16))
        await self.reject(f,context_id=255)
        await self.reject(f,keep=0)
        self.coverage.hit('binding')
        await self.reject(f,user_metadata=metadata(f,1,self.epoch))
        self.coverage.hit('sequence')
        if self.p['NOC_PROFILE']:
            request=flows[2]
            await self.step(i_response_reserved=0)
            await self.reject(request)
            await self.step(i_response_reserved=(1<<(n*tx))-1)
            self.coverage.hit('request_reservation')
        for flow in flows:await self.send(flow)
        await self.idle()
        assert self.coverage.classes==set(classes)
        self.coverage.hit('all_classes')
        # Saturate ordinary RX while the dedicated event ejection keeps progressing.
        await self.step(i_tile_rx_ready=0)
        for _ in range(4):await self.send(f)
        await self.wait(60)
        assert not self.last.post['o_idle']
        if self.p['NOC_PROFILE']:
            await self.step(i_tile_rx_ready=1<<((n-1)*rx+rx-1))
            before=self.coverage.counts['delivered']
            await self.send(flows[4])
            for _ in range(400):
                await self.step()
                if self.coverage.counts['delivered']>before:break
            else:raise AssertionError('Critical VC blocked behind data')
            self.coverage.hit('critical_progress')
        # A selected-flow drain blocks its new beats, preserving pending traffic.
        await self.step(i_drain_valid=1,i_drain_flow_mask=1,i_drain_all=0,i_drain_tag=77)
        assert self.last.pre['o_drain_ready']
        await self.step(i_drain_valid=0)
        await self.reject(f)
        await self.step(i_tile_rx_ready=(1<<(n*rx))-1)
        for _ in range(3000):
            await self.step()
            if self.last.pre['o_lifecycle_valid']:
                assert self.last.pre['o_lifecycle_status']==0
                assert self.last.pre['o_lifecycle_tag']==77
                break
        else:raise AssertionError('Selected drain did not finish')
        self.coverage.hit('selected_drain')
        await self.step(i_run=0)
        await self.step(i_run=1)
        await self.idle()
        if self.p['DRAIN_TIMEOUT_CYCLES']<=256:
            await self.step(i_tile_rx_ready=0)
            await self.send(f)
            await self.lifecycle('drain',all_flows=1,status=2)
            assert not self.last.pre['o_idle'],'Timeout discarded traffic'
            self.coverage.hit('timeout')
            await self.step(i_tile_rx_ready=(1<<(n*rx))-1,i_run=0)
            await self.idle()
            await self.step(i_run=1)
        await self.step(i_tile_rx_ready=0)
        for _ in range(2):await self.send(f)
        await self.wait(10)
        assert self.last.post['o_flow_outstanding']
        old_epoch=self.epoch
        await self.lifecycle('flush',status=1)
        self.epoch=self.last.post['o_execution_epoch'];self.sequence.clear()
        assert self.epoch==old_epoch+1
        assert self.last.post['o_flow_outstanding']==0
        self.coverage.hit('flush')
        await self.step(i_run=0,i_tile_rx_ready=(1<<(n*rx))-1)
        await self.step(i_run=1)
        await self.reject(f,user_metadata=metadata(f,0,old_epoch))
        self.coverage.hit('stale_epoch')
        await self.send(f)
        await self.idle()
        await self.lifecycle('drain',all_flows=1)
        await self.step(i_run=0)
        # Revalidate the post-flush epoch before isolating the reachability check.
        candidate_flows=[flow.copy() for flow in flows]
        for index,flow in enumerate(candidate_flows):
            flow[0]=(flow[0]&~(255<<33))|(self.epoch<<33)
            await self.cfg(CFG_WRITE,index=2+n+4*index,data=flow[0])
        words=image(self.p,candidate_flows)
        await self.cfg(CFG_VALIDATE,crc=crc32c(words))
        # Active route faults reject the candidate without changing active state.
        await self.cfg(CFG_WRITE,index=2,data=1)
        words[2]=1
        await self.cfg(CFG_VALIDATE,crc=crc32c(words),status=BAD_IMAGE)
        await self.cfg(CFG_WRITE,index=2,data=0)
        words[2]=0
        await self.cfg(CFG_VALIDATE,crc=crc32c(words))
        self.coverage.hit('fault_rejection')
        # Reset interrupts live traffic and clears configuration/epochs/credits coherently.
        await self.step(i_run=0)
        await self.step(i_run=1,i_tile_rx_ready=0)
        if self.p['ENABLE_LINK_PARITY']:
            self.active.update(inject_parity=True,fault_applied=False,expect_fatal=True)
        await self.send(f)
        if self.p['ENABLE_LINK_PARITY']:
            for _ in range(20):
                await self.step()
                if self.active.get('fault_applied') and self.last.post['o_fatal_error']:break
            else:raise AssertionError('Link parity fault escaped containment')
            assert not self.last.post['o_tile_rx_valid']
            self.active['inject_parity']=False
            self.coverage.hit('parity_containment')
        else:await self.wait(8)
        await self.wait(3,i_noc_rstb=0,i_tile_tx_valid=0)
        self.active['expect_fatal']=False
        self.epoch=0;self.version=0;self.sequence.clear()
        await self.wait(5,i_noc_rstb=1,i_run=0,i_tile_rx_ready=(1<<(n*rx))-1)
        assert not self.last.post['o_configured']
        self.coverage.hit('reset_pending')
        # Every source/destination pair is reached through actual router/TNI instances.
        print('Global NoC: all-pairs routing',flush=True)
        for offset in range(n):
            routes=[flow_words(flow_id=201+s,source=s,destination=(s+offset)%n)
                    for s in range(n)]
            await self.load(routes)
            offers={s*tx:self.beat(flow) for s,flow in enumerate(routes)}
            for _ in range(3000):
                item=await self.step(**self.offers(offers))
                accepted=[i for i in offers if item.pre['o_tile_tx_ready']>>i&1]
                for i in accepted:self.advance(offers.pop(i))
                if not offers:break
            else:raise AssertionError('All-pairs injection stalled')
            await self.idle()
        assert len(self.coverage.pairs)==n*n,(n,self.coverage.pairs)
        self.coverage.hit('all_pairs')
        # Hold offers until accepted, randomize independent endpoint backpressure,
        # and keep multiple packet streams active concurrently.
        print('Global NoC: randomized concurrent traffic',flush=True)
        offers={}
        for _ in range(self.c.random_cycles):
            for s,flow in enumerate(routes):
                if s*tx not in offers and self.rng.random()<0.35:
                    offers[s*tx]=self.beat(flow)
            item=await self.step(**self.offers(offers),
                i_tile_rx_ready=self.rng.getrandbits(n*rx))
            for i in list(offers):
                if item.pre['o_tile_tx_ready']>>i&1:self.advance(offers.pop(i))
            self.coverage.random_cycles+=1
        for _ in range(3000):
            item=await self.step(**self.offers(offers),i_tile_rx_ready=(1<<(n*rx))-1)
            for i in list(offers):
                if item.pre['o_tile_tx_ready']>>i&1:self.advance(offers.pop(i))
            if not offers:break
        else:raise AssertionError('Random offers did not retire')
        self.coverage.hit('random')
        await self.idle()
        await self.lifecycle('drain',all_flows=1)
        await self.wait(4)
