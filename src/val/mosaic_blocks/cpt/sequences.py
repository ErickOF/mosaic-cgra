"""Shell-only programming, primitive mappings and mapper-owned replay sequences."""
from cpt.model import context, pack, command, event, unpack, RECORD
from cpt.transaction import CptItem, INPUTS
from tile_shell.model import number, crc32c
from tile_shell.sequences import TileShellSequence

class CptSequence(TileShellSequence):
    def __init__(self, config):
        super().__init__(config)
        self.base = {n:self.base.get(n,0) for n in INPUTS}
        self.base.update(i_rstb=1,i_cfg_rstb=1,i_body_power_good=1)
        self.active=None

    async def cycle(self, label='idle', *, core_edge=True, cfg_edge=None, fault=None, **ports):
        self.index += 1
        import os
        if os.getenv('CPT_DEBUG_CYCLES'):
            print(self.index, label, flush=True)
        auto = dict(i_body_save_done=number(self.last.get('o_body_save', '0')) or 0,
                    i_body_restore_done=number(self.last.get('o_body_restore', '0')) or 0,
                    i_body_isolation_ack=number(self.last.get('o_body_isolate', '0')) or 0)
        if 'o_body_power_enable' in self.last:
            auto['i_body_power_good'] = number(self.last['o_body_power_enable'])
        item = CptItem(f'{label}_{self.index}', self.base | auto | ports,
            cfg_edge=(self.index % 3 != 0) if cfg_edge is None else cfg_edge,
            core_edge=core_edge, phase=self.index % 2, fault=fault)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.post
        for domain, raw in item.edges.items():
            p = {n: number(v) for n, v in raw.items()}
            if domain == 'cfg' or domain == 'core' and not self.c.CONFIG_ASYNC:
                if p['o_cfg_response_valid'] and p['i_cfg_response_ready']:
                    self.responses[p['o_cfg_response_tag']] = p
            if domain == 'core' and p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
                self.runtime_responses[p['o_runtime_response_tag']] = p
        return item

    async def reset(self, cfg_only=False, fault=None):
        self.base['i_data_in_valid'] = 0
        self.base['i_predicate_in_valid'] = 0
        await super().reset(cfg_only, fault)
        if self.active:
            self.active['contexts'].clear()

    async def cfg_response(self, tag):
        for _ in range(20000):
            if tag in self.responses:
                return self.responses.pop(tag)
            await self.cycle()
        raise AssertionError(f'Configuration response timeout, tag {tag}')

    async def runtime(self, command, context=0, owner=5, kernel=9, *, wait=True):
        return await super().runtime(command, context, owner, kernel, wait=wait)

    def context(self, **changes):
        return context(self.c.parameters, **changes)

    async def provision(self, ctx, cid=0, *, activate=True, error=False):
        image=pack(self.c.parameters,ctx)
        self.active['contexts'][cid]=ctx.copy()
        for word in range(self.c.CONFIG_WORD_COUNT):
            response=await self.cfg(0,cid,word,image >> (64*word) & ((1 << 64)-1))
            assert not number(response['o_cfg_response_error']),response
        crc=crc32c(image.to_bytes(self.c.CONFIG_WORD_COUNT*8,'little'))
        response=await self.cfg(2,cid,crc=crc)
        assert bool(number(response['o_cfg_response_error']))==error,response
        if error:self.coverage.hit('validation_rejection')
        elif activate:
            response=await self.cfg(3,cid)
            assert not number(response['o_cfg_response_error']),response
            await self.idle(8)
        return response

    async def setup(self, **changes):
        await self.reset()
        self.active.update(events=[],outputs=[],loops=[])
        response=await self.runtime(0)
        assert not number(response['o_runtime_response_error']),tuple((n,number(response[n])) for n in ('o_runtime_response_error_code','o_status_error_code','o_status_fatal_error','o_status_quiescent'))
        ctx=self.ctx=self.context(**changes)
        await self.provision(ctx)
        assert number(self.last['o_status_tile_class'])==4
        assert not number((await self.runtime(1))['o_runtime_response_error'])
        await self.idle(80)
        assert not number(self.last['o_status_fatal_error']),self.last
        self.identity=number(self.last['o_status_active_context']) | number(
            self.last['o_status_context_version']) << self.c.aliases['CI']

    async def send(self, cls, opcode, a=0, b=0, *, expected=None, error=None,
                   predicate=None, blocked=0, auxiliary=None, **fields):
        self.command_tag=(getattr(self,'command_tag',0)+1)%256
        fields.setdefault('tag',self.command_tag)
        if predicate is not None:fields['predicate_enable']=1
        if auxiliary is not None:fields['auxiliary']=1
        data,meta=command(self.c.parameters,self.identity,cls,opcode,a,b,**fields)
        start=len(self.active['outputs'])
        accepted=False
        auxiliary_accepted=auxiliary is None
        pred_port=fields.get("predicate_port",0)
        pred_accepted=predicate is None
        for tick in range(1000):
            ports=dict(i_data_in_valid=int(not accepted) | int(not auxiliary_accepted)<<1,
                i_data_in_payload=data | (auxiliary or 0)<<64,
                i_data_in_metadata=meta | self.identity<<128,
                i_predicate_in_valid=int(not pred_accepted)<<pred_port,
                i_predicate_in_payload=(predicate or 0)<<(pred_port*self.c.PREDICATE_LANES),
                i_predicate_in_metadata=self.identity<<(pred_port*64),
                i_data_out_ready=int(tick>=blocked))
            item=await self.cycle('command',**ports)
            edge={n:number(v) for n,v in item.edges['core'].items()}
            if edge['i_data_in_valid'] and edge['o_data_in_ready']&1:accepted=True
            if edge['i_data_in_valid']>>1 & edge['o_data_in_ready']>>1 & 1:auxiliary_accepted=True
            if edge['i_predicate_in_valid']>>pred_port & edge['o_predicate_in_ready']>>pred_port & 1:pred_accepted=True
            results=[(v,m) for p,v,m in self.active['outputs'][start:]
                if p=='data' and m>>124==11 and m>>96&255==fields['tag']]
            suppressed=predicate==0 and not fields.get('false_token')
            if results or accepted and suppressed and tick>15:
                if results:
                    value,rm=results[0]
                    assert len(results)==1
                    if expected is not None:assert value==expected,(cls,opcode,value,expected)
                    if error is not None:assert bool(rm>>121&1)==error,(cls,opcode,rm,error)
                await self.idle(5)
                assert not number(self.last['o_status_fatal_error'])
                if blocked:self.coverage.hit('backpressure')
                return results[0] if results else None
        raise AssertionError(('Command timeout',cls,opcode,self.last))

    async def incoming(self, kind=0, **fields):
        raw=event(self.c.parameters,self.identity,kind,**fields)
        for _ in range(300):
            item=await self.cycle('event',i_event_in_valid=1,i_event_in_payload=raw)
            if number(item.edges['core']['o_event_in_ready']):break
        else:raise AssertionError('Event ingress timeout')
        await self.idle(16)
        return raw

    async def body(self):
        await self.setup()
        await self.send(0,1,write_enable=1,expected=self.ctx['lane_mask'])
        self.coverage.hit('predicate')
        lanes=self.ctx['lane_mask']
        await self.send(0,2,0x55,write_enable=1,destination=1)
        for op in range(3,8):
            await self.send(0,op,source_a=0,source_b=1,write_enable=1,destination=2)
        await self.send(0,8,write_enable=1,destination=2,mask=1)
        await self.send(0,3,source_a=2,mask=1,error=True)
        self.coverage.hit('predicate')
        for op in range(8):
            for sign in (0,1):
                for a,b in ((0,0),(0xffffffff,0),(0x80000000,0x7fffffff),(1,2)):
                    await self.send(1,op,a,b,signed=sign,write_enable=1,destination=min(3,self.c.PREDICATE_DEPTH-1),
                        blocked=18 if op==0 else 0)
        self.coverage.hit('comparison')
        await self.send(1,0,42,0,auxiliary=42,expected=lanes)
        await self.send(1,0,42,0,auxiliary=41,expected=0)
        if self.c.PREDICATE_INPUT_PORTS>1:
            await self.send(1,0,1,1,predicate=1,predicate_port=1,expected=lanes)
        for typ in range(1,7):
            await self.send(7,1,0xc001+typ,destination=0,register_type=typ,error=False)
            await self.send(7,0,source_a=0,register_type=typ,expected=0xc001+typ,error=False)
            await self.send(1,0,0,0xc001+typ,source_a=0,rf_a=1,register_type=typ,
                expected=lanes,error=False)
        await self.send(7,2,destination=0,error=False)
        await self.send(7,0,source_a=0,error=True)
        await self.send(0,2,predicate=5 & lanes,predicate_load=1,expected=5 & lanes)
        self.coverage.hit('registers')
        await self.send(4,0,object_id=0,predicate=0)
        await self.send(7,3,object_id=0,expected=0)
        if self.c.SUPPORT_PREDICATED_TOKEN:
            await self.send(4,0,object_id=0,predicate=0,false_token=1,expected=0)
        self.coverage.hit('false_suppress')
        # Deterministic random Boolean and exact comparison mappings.
        for n in range(self.c.random_cycles):
            if n%3:
                await self.send(1,self.rng.randrange(8),self.rng.getrandbits(32),
                    self.rng.getrandbits(32),signed=self.rng.randrange(2))
            else:
                await self.send(0,self.rng.randrange(3),self.rng.getrandbits(self.c.PREDICATE_LANES),
                    mask=self.rng.randrange(1,lanes+1),write_enable=1,
                    destination=self.rng.randrange(self.c.PREDICATE_DEPTH))
            self.coverage.random_cycles+=1
        self.coverage.hit('random')
        # Counts, reliable per-source ordering and owner/version checks.
        await self.incoming(event_id=0,sequence=0)
        await self.send(7,3,object_id=0,expected=1)
        await self.incoming(event_id=0,sequence=0)
        await self.incoming(event_id=0,sequence=2)
        await self.send(7,3,object_id=0,expected=1)
        self.coverage.hit('duplicate')
        await self.incoming(event_id=0,sequence=1,owner=6)
        await self.incoming(event_id=0,sequence=1,epoch=2)
        await self.send(7,3,object_id=0,expected=1)
        self.coverage.hit('ownership')
        await self.incoming(event_id=0,sequence=1)
        await self.send(7,3,object_id=0,expected=2)
        await self.send(4,1,object_id=0)
        await self.send(7,3,object_id=0,expected=1)
        await self.send(4,2,object_id=0)
        await self.send(7,3,object_id=0,expected=0)
        self.coverage.hit('events')
        # Full counts stall without wrapping. Clearing frees the pending post.
        count=(1<<self.c.EVENT_COUNT_WIDTH)-1
        for _ in range(count):await self.send(4,0,object_id=0)
        await self.send(7,3,object_id=0,expected=count)
        await self.send(4,2,object_id=0)
        self.coverage.hit('saturation')
        for mode,name in ((3,'wait_any'),(4,'wait_all')):
            event_mask=3 if self.c.NUM_EVENTS>=2 else 1
            await self.send(4,mode,object_id=0,mask=event_mask,consume=1,tag=71)
            await self.send(4,0,object_id=0)
            if mode==4 and self.c.NUM_EVENTS>=2:await self.send(4,0,object_id=1)
            await self.idle(20)
            matches=[unpack(RECORD,e) for e in self.active['events']
                if e>>32&15==2 and e>>128&255==71]
            assert matches and matches[-1]['payload']&0xffff==(1 if mode==3 else event_mask)
            await self.send(7,3,object_id=0,expected=0)
            self.coverage.hit(name)
        await self.send(4,3,object_id=0,mask=1,tag=72)
        await self.send(4,5,object_id=0,tag=73,error=True)
        await self.send(4,5,object_id=0,tag=72)
        await self.idle(12)
        assert any(e>>32&15==2 and e>>60&1 for e in self.active['events'])
        # Unique arrivals and two reusable generations, with duplicate rejection.
        participants=(1<<min(self.c.MAX_PARTICIPANTS,3))-1
        for generation in range(2):
            if generation==0:await self.send(5,0,participants,object_id=0,tag=81)
            for part in range(participants.bit_length()):
                await self.send(5,1,object_id=0,participant=part,generation=generation)
                if part==0 and participants>1:
                    await self.send(5,1,object_id=0,participant=part,generation=generation,error=True)
            await self.idle(12)
            releases=[unpack(RECORD,e) for e in self.active['events'] if e>>32&15==3]
            assert len(releases)==generation+1
            assert releases[-1]['participants']==participants
            assert releases[-1]['payload']==generation
            await self.send(7,4,object_id=0,expected=generation+1)
        self.coverage.hit('barrier')
        # Idle suspension preserves compact architectural state.
        await self.send(7,1,0x1234,destination=0,register_type=1)
        assert not number((await self.runtime(2))['o_runtime_response_error'])
        await self.idle(10)
        assert number(self.last['o_status_execution_state'])==9
        assert not number((await self.runtime(3))['o_runtime_response_error'])
        await self.send(7,0,source_a=0,register_type=1,expected=0x1234)
        self.coverage.hit('suspend_resume')
        if self.c.FU_PROFILE:
            seq=2
            for op in (0,1,2,3,4,5,6,8):
                if op==5 and not self.c.SUPPORT_CONTEXT_COORDINATION:continue
                if op!=5 and not self.c.SUPPORT_CLUSTER_LIFECYCLE:continue
                atag=100+op
                await self.send(6,op,tag=atag,error=False)
                await self.idle(12)
                assert any(e>>32&15==5 and e>>128&255==atag for e in self.active['events'])
                await self.incoming(7,opcode=op,tag=atag,participants=self.ctx['targets'],sequence=seq)
                seq+=1
                # Source IDs isolate these individual transport sessions.
                # Re-establish exact sequences for the response below.
                await self.incoming(6,opcode=op,tag=atag,sequence=seq)
                seq+=1
                await self.idle(20)
                assert any(e>>32&15==9 and e>>128&255==atag for e in self.active['events'])
            self.coverage.hit('action')
        # Bounded, signed multi-level loops and fully delivered token framing.
        depth=self.c.MAX_LOOP_DEPTH
        levels=[(-2,0,1,2,0,0) if n%2==0 else (3,0,-1,2,0,0) for n in range(depth)]
        await self.setup(loop_depth=depth,levels=levels,loop_ii=3)
        await self.send(3,0,tag=91,error=False,blocked=25)
        await self.idle(5000)
        frames=[self.active['loops'][i:i+3] for i in range(0,len(self.active['loops']),3)]
        assert len(frames)==2**depth,(len(frames),depth)
        for n,frame in enumerate(frames):
            assert len(frame)==3
            assert [p for p,_ in frame]==[n,(-2+n%2)&((1<<64)-1),n%2]
            assert frame[0][1]>>122&1 and frame[-1][1]>>123&1
        self.coverage.hit('loop')
        # Drain reaches a safe boundary after all accepted effects.
        assert not number((await self.runtime(4))['o_runtime_response_error'])
        await self.idle(20)
        assert number(self.last['o_status_execution_state'])in (2,11)
        self.coverage.hit('drain')
        # Reject an illegal package through the real CFG_VALIDATE handshake.
        await self.reset()
        assert not number((await self.runtime(0))['o_runtime_response_error'])
        await self.provision(self.context(magic=0),error=True)
        bad_levels=[(0,0,0,1,0,0)]+[(0,0,0,0,0,0)]*(self.c.MAX_LOOP_DEPTH-1)
        await self.provision(self.context(levels=bad_levels),error=True)
        bad_levels=[(0,4,1,3,1,0)]+[(0,0,0,0,0,0)]*(self.c.MAX_LOOP_DEPTH-1)
        await self.provision(self.context(levels=bad_levels),error=True)
        # An accepted command remains stable under unknown output readiness;
        # reset explicitly cancels its unconsumed result and predicate copies.
        await self.setup()
        data,meta=command(self.c.parameters,self.identity,0,1,write_enable=1,tag=222)
        self.base.update(i_data_out_ready=0,i_predicate_out_ready=0)
        for _ in range(20):
            item=await self.cycle('pending_reset',i_data_in_valid=1,i_data_in_payload=data,
                i_data_in_metadata=meta)
            if number(item.edges['core']['o_data_in_ready'])&1:break
        await self.idle(15)
        assert number(self.last['o_data_out_valid'])==1
        held=(self.last['o_data_out_payload'],self.last['o_data_out_metadata'])
        await self.idle(4,i_data_out_ready='x',i_predicate_out_ready='x'*self.c.PREDICATE_OUTPUT_PORTS)
        assert number(self.last['o_data_out_valid'])==1
        assert held==(self.last['o_data_out_payload'],self.last['o_data_out_metadata'])
        self.coverage.hit('unknown_ready')
        await self.idle(3,i_rstb='x')
        assert number(self.last['o_data_out_valid'])==0
        await self.idle(2)
        assert held==(self.last['o_data_out_payload'],self.last['o_data_out_metadata'])
        self.coverage.hit('unknown_reset')
        self.base.update(i_data_out_ready=1,i_predicate_out_ready=(1<<self.c.PREDICATE_OUTPUT_PORTS)-1)
        await self.reset()
        assert number(self.last['o_data_out_valid'])==0
        assert number(self.last['o_predicate_out_valid'])==0
        self.coverage.hit('reset_pending')
        if self.c.FU_PROFILE and self.c.SUPPORT_TIMEOUT and self.c.SUPPORT_CLUSTER_LIFECYCLE:
            await self.setup(timeout=12)
            await self.send(6,0,tag=151,error=False)
            await self.idle(80)
            records=[unpack(RECORD,e) for e in self.active['events']]
            assert sum(r['kind']==5 and r['tag']==151 for r in records)==1
            assert sum(r['kind']==8 and r['tag']==151 for r in records)==1
            assert not any(r['kind']==9 and r['tag']==151 for r in records)
            await self.incoming(6,opcode=0,tag=151,sequence=0)
            await self.idle(20)
            assert sum(e>>32&15==9 and e>>128&255==151 for e in self.active['events'])==1
            self.coverage.hit('timeout_query')
            await self.send(6,0,tag=152,error=False)
            await self.incoming(6,opcode=0,tag=152,sequence=1,flags=1)
            await self.idle(20)
            assert any(e>>32&15==9 and e>>128&255==152 and e>>60&1
                for e in self.active['events'])
            self.coverage.hit('rejection')
            await self.reset()

        await self.setup(levels=[(0,0,1,12,0,0)]+[(0,0,0,0,0,0)]*(self.c.MAX_LOOP_DEPTH-1),
            loop_ii=4)
        await self.send(3,0,tag=93)
        assert not number((await self.runtime(2))['o_runtime_response_error'])
        await self.idle(10)
        assert number(self.last['o_status_execution_state'])==9
        saved=len(self.active['loops'])
        await self.idle(20)
        assert len(self.active['loops'])==saved
        assert not number((await self.runtime(3))['o_runtime_response_error'])
        await self.idle(1200)
        assert len(self.active['loops'])==36
        assert any(e>>32&15==4 and e>>128&255==93 for e in self.active['events'])
        self.coverage.hit('loop_suspend')
        await self.reset()
        if self.c.FU_PROFILE and self.c.SUPPORT_CLUSTER_LIFECYCLE:
            await self.setup()
            await self.send(6,0,tag=160)
            rtag=await self.runtime(4,wait=False)
            await self.incoming(7,opcode=0,tag=160,participants=self.ctx['targets'],sequence=0)
            await self.incoming(6,opcode=0,tag=160,sequence=1)
            await self.idle(30)
            assert rtag in self.runtime_responses
            assert not number(self.runtime_responses[rtag]['o_runtime_response_error'])
            assert sum(e>>32&15==9 and e>>128&255==160 for e in self.active['events'])==1
            self.coverage.hit('action_drain')
            await self.reset()

        await self.setup(command_limit=1)
        await self.send(1,0,7,7,expected=(1<<self.c.PREDICATE_LANES)-1)
        await self.idle(30)
        assert number(self.last['o_status_execution_state'])==11
        assert sum(e&7==0 for e in self.active['events'])==1
        self.coverage.hit('completion')
        await self.reset()
        if self.c.CONTEXT_DEPTH>1:
            await self.reset()
            assert not number((await self.runtime(0))['o_runtime_response_error'])
            await self.provision(self.context(command_limit=1),cid=1,activate=False)
            await self.provision(self.context(command_limit=1,sequence_enable=1,
                terminal_context=0,next_context=1))
            self.active.update(events=[],outputs=[],loops=[])
            assert not number((await self.runtime(1))['o_runtime_response_error'])
            await self.idle(80)
            self.identity=number(self.last['o_status_context_version'])<<self.c.aliases['CI']
            await self.send(1,0,1,1,expected=(1<<self.c.PREDICATE_LANES)-1)
            await self.idle(80)
            assert number(self.last['o_status_active_context'])==1
            self.identity=1 | number(self.last['o_status_context_version'])<<self.c.aliases['CI']
            await self.send(1,1,1,1,expected=0)
            await self.idle(30)
            assert number(self.last['o_status_execution_state'])==11
            assert sum(e&7==0 for e in self.active['events'])==1
            self.coverage.hit('context_chain')
            await self.reset()

        if self.c.EVENT_PROTECTION:
            await self.setup()
            await self.send(4,3,object_id=0,mask=1,tag=175)
            self.active['expect_fatal']=True
            await self.cycle('event_policy_fault',fault=('event',0,1))
            await self.idle(20)
            assert number(self.last['o_status_fatal_error'])==1
            data,meta=command(self.c.parameters,self.identity,0,1,tag=176)
            for _ in range(10):
                await self.cycle('fatal_containment',i_data_in_valid=1,
                    i_data_in_payload=data,i_data_in_metadata=meta)
                assert number(self.last['o_data_in_ready'])==0
                assert number(self.last['o_data_out_valid'])==0
                assert number(self.last['o_predicate_out_valid'])==0
            await self.cycle('release_fault',i_rstb=0,i_cfg_rstb=0,fault=('release',0,0))
            await self.reset()
            self.active['expect_fatal']=False
            self.coverage.hit('event_fault')

        # Bounded descending loops and zero-trip completion are distinct from a
        # counted nonempty loop; neither may fabricate an extra frame.
        for levels,count,run in (
            ([(2,-2,-1,4,1,2)],4,94),
            ([(0,0,0,0,0,0)],0,95),
        ):
            levels=levels+[(0,0,0,0,0,0)]*(self.c.MAX_LOOP_DEPTH-1)
            await self.setup(levels=levels)
            await self.send(3,0,tag=run,error=False)
            await self.idle(300)
            assert len(self.active['loops'])==3*count
            for n in range(count):
                values=[v for v,_ in self.active['loops'][n*3:n*3+3]]
                assert values==[n,(2-n)&((1<<64)-1),n]
            completed=[unpack(RECORD,e) for e in self.active['events'] if e>>32&15==4]
            assert len(completed)==1 and completed[0]['tag']==run
            assert completed[0]['payload']==count
            self.coverage.hit('bounded_loop' if count else 'zero_trip')
            await self.reset()
        if self.c.LOOP_EXPORT_LEVELS>1:
            levels=[(0,0,1,2,0,0),(5,0,-1,2,0,0)]+[(0,0,0,0,0,0)]*(self.c.MAX_LOOP_DEPTH-2)
            await self.setup(levels=levels,loop_depth=2,loop_export=3)
            await self.send(3,0,tag=96)
            await self.idle(500)
            assert len(self.active['loops'])==20
            for n in range(4):
                assert [v for v,_ in self.active['loops'][5*n:5*n+5]]==[
                    n,n%2,n%2,5-n//2,n//2]
            self.coverage.hit('multiple_exports')
            await self.reset()
