"""Check public token conservation, reference results and stable held channels."""
from collections import deque
from pyuvm import ConfigDB, uvm_subscriber
from cpt.model import Architecture, unpack, META
from tile_shell.model import number

class CptScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c=ConfigDB().get(self,'','config')
        self.active=ConfigDB().get(self,'','active')
        self.coverage=ConfigDB().get(self,'','coverage')
        self.model=Architecture(self.c.parameters)
        self.inputs=[deque(),deque()]
        self.predicate_inputs=[deque() for _ in range(self.c.PREDICATE_INPUT_PORTS)]
        self.commands=deque()
        self.expected=deque()
        self.predicates=[deque() for _ in range(self.c.PREDICATE_OUTPUT_PORTS)]
        self.holds={}

    def discard(self):
        self.coverage.counts['cancelled_inputs']+=sum(len(q) for q in self.inputs)
        self.coverage.counts['cancelled_commands']+=len(self.commands)
        self.coverage.counts['cancelled_data']+=len(self.expected)
        self.coverage.counts['cancelled_predicates']+=sum(len(q) for q in self.predicates)
        self.coverage.counts['cancelled_predicate_inputs']+=sum(len(q) for q in self.predicate_inputs)
        for q in self.inputs:q.clear()
        self.commands.clear();self.expected.clear()
        for q in (*self.predicates,*self.predicate_inputs):q.clear()
        self.holds.clear()
        self.model=Architecture(self.c.parameters)

    def write(self,obs):
        if obs.domain!='core':return
        self.coverage.cycles+=1
        p={n:number(v) for n,v in obs.ports.items()}
        b={n:number(v) for n,v in obs.body.items()}
        if p['i_rstb']==0 or b['o_body_flush']:
            self.discard();return
        if p['i_rstb'] is None:return
        assert not b['fatal'] or self.active.get('expect_fatal'), ('Fatal', b)
        if b['context_change']:
            assert not self.commands and not self.expected,'Live context replacement'
            self.model=Architecture(self.c.parameters)
            self.coverage.hit('activation')
        for port in range(2):
            if p['i_data_in_valid'] >> port & p['o_data_in_ready'] >> port & 1:
                self.inputs[port].append((p['i_data_in_payload'] >> (64*port) & ((1<<64)-1),
                    p['i_data_in_metadata'] >> (128*port) & ((1<<128)-1)))
                self.coverage.counts['accepted_inputs']+=1
        for port in range(self.c.PREDICATE_INPUT_PORTS):
            if p['i_predicate_in_valid']>>port & p['o_predicate_in_ready']>>port & 1:
                self.predicate_inputs[port].append(p['i_predicate_in_payload'] >>
                    (port*self.c.PREDICATE_LANES) & ((1<<self.c.PREDICATE_LANES)-1))
                self.coverage.counts['accepted_predicate_inputs']+=1
        if b['issue']:
            assert self.inputs[0],'Unaccepted command'
            data,meta=self.inputs[0].popleft()
            self.coverage.counts['consumed_inputs']+=1
            if meta>>60&1:
                assert self.inputs[1],'Missing joined auxiliary operand'
                aux,auxmeta=self.inputs[1].popleft()
                data=data&0xffffffff | (aux&0xffffffff)<<32
                self.coverage.counts['consumed_inputs']+=1
            m=unpack(META,meta)
            ctx=self.active['contexts'][b['o_body_context_id']]
            if ctx['command_class']!=8:
                meta=meta & ~(15<<32) | ctx['command_class']<<32
            external=0
            if meta>>54&1:
                port=meta>>61&1
                assert self.predicate_inputs[port],'Missing predicate token'
                external=self.predicate_inputs[port].popleft()
                self.coverage.counts['consumed_predicate_inputs']+=1
            self.commands.append(dict(data=data,meta=meta,done=False,external=external))
            self.coverage.counts['issued']+=1
        if b['execute'] and self.commands and not self.commands[0]['done']:
            q=self.commands[0]
            ctx=self.active['contexts'][b['o_body_context_id']]
            condition=not(q['meta']>>54&1) or bool(q['external'] & ctx['lane_mask'] &
                (q['meta']>>64&0xffff))
            assert bool(b['command_condition'])==condition,'Wrong predicate qualification'
            e=self.model.evaluate(q['data'],q['meta'],condition,q['external'])
            m=unpack(META,q['meta'])
            # Event/loop/coordination outcomes are checked through directed
            # architectural observations; their acks still obey exact accounting.
            checked=m['command_class'] in (0,1,7) and not (m['command_class']==7 and m['opcode']>=3)
            if not e['suppress']:
                self.coverage.counts['reserved_data']+=1
                self.expected.append((e['data'] if checked else None,e['error'] if checked else None,m['tag']))
            if e['predicate'] is not None and not e['error']:
                ctx=self.active['contexts'][b['o_body_context_id']]
                for port,queue in enumerate(self.predicates):
                    if ctx['predicate_route']>>port&1:
                        queue.append(e['predicate'])
                        self.coverage.counts['reserved_predicates']+=1
            q['done']=True
        if b['retire']:
            assert self.commands and self.commands[0]['done'],'Unreserved retirement'
            self.commands.popleft()
            self.coverage.counts['retired']+=1
        for prefix,width,count in [('data',64,1),('predicate',self.c.PREDICATE_LANES,self.c.PREDICATE_OUTPUT_PORTS),('event',256,1)]:
            for port in range(count):
                valid=p[f'o_{prefix}_out_valid']>>port&1
                ready=p[f'i_{prefix}_out_ready']
                r=None if ready is None else ready>>port&1
                payload=p[f'o_{prefix}_out_payload']
                payload=None if payload is None else payload>>(port*width)&((1<<width)-1)
                meta=0 if prefix=='event' else p[f'o_{prefix}_out_metadata']>>(port*(128 if prefix=='data' else 64))&((1<<(128 if prefix=='data' else 64))-1)
                key=(prefix,port)
                if key in self.holds:assert valid and (payload,meta)==self.holds[key],('Unstable',key)
                if valid and r!=1:self.holds[key]=(payload,meta)
                else:self.holds.pop(key,None)
                if not(valid and r==1):continue
                if prefix=='data' and meta>>124==11:
                    assert self.expected,'Duplicate command result'
                    data,error,tag=self.expected.popleft()
                    if data is not None:assert payload==data,('Result',payload,data,tag)
                    if error is not None:assert bool(meta>>121&1)==error,('Error flag',meta,error)
                    assert meta>>96&255==tag
                    self.coverage.counts['data_results']+=1
                elif prefix=='predicate':
                    assert self.predicates[port],'Unreserved predicate copy'
                    assert (payload,meta>>32&((1<<width)-1))==self.predicates[port].popleft()
                    self.coverage.counts['predicate_copies']+=1
                elif prefix=='event':
                    self.active.setdefault('events',[]).append(payload)
                    self.coverage.counts['events_delivered']+=1
                elif prefix=='data':
                    self.active.setdefault('loops',[]).append((payload,meta))
                    self.coverage.counts['loop_beats']+=1
                self.active.setdefault('outputs',[]).append((prefix,payload,meta))

    def check_phase(self):
        assert all(not q for q in self.inputs) and not self.commands and not self.expected
        assert all(not q for q in (*self.predicates,*self.predicate_inputs))
        c=self.coverage.counts
        assert c['accepted_inputs']==c['consumed_inputs']+c['cancelled_inputs']
        assert c['issued']==c['retired']+c['cancelled_commands']
        assert c['reserved_data']==c['data_results']+c['cancelled_data']
        assert c['reserved_predicates']==c['predicate_copies']+c['cancelled_predicates']
        assert c['accepted_predicate_inputs']==c['consumed_predicate_inputs']+c['cancelled_predicate_inputs']
