"""Check public token conservation and independent numerical/state retirement."""
from collections import deque
from pyuvm import ConfigDB, uvm_subscriber
from sft.model import Architecture, pack, required
from tile_shell.model import number


class SftScoreboard(uvm_subscriber):
    def build_phase(self):
        super().build_phase()
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = Architecture(self.c.parameters)
        self.inputs = [deque() for _ in range(2)]
        self.predicates = deque()
        self.operations = deque()
        self.outputs = [deque() for _ in range(self.c.DATA_OUTPUT_PORTS)]
        self.holds = {}
        self.ctx = None
        self.cycles = 0
        self.completion_seen=0
        self.was_complete=False

    def discard(self):
        if self.was_complete:assert self.completion_seen==1, 'Missing completion event'
        self.completion_seen=0
        self.was_complete=False
        self.coverage.counts['cancelled_operations'] += len(self.operations)
        self.coverage.counts['cancelled_inputs'] += sum(len(q) for q in self.inputs)
        self.coverage.counts['cancelled_copies'] += sum(len(q) for q in self.outputs)
        self.operations.clear()
        for q in (*self.inputs, *self.outputs, self.predicates): q.clear()
        self.holds.clear()
        self.model.reset()
        self.ctx = None

    def write(self, obs):
        if obs.domain != 'core': return
        self.cycles += 1
        self.coverage.cycles=self.cycles
        p = {n: number(v) for n,v in obs.ports.items()}
        b = {n: number(v) for n,v in obs.body.items()}
        c, coverage = self.c, self.coverage
        if p['i_rstb'] == 0 or p['o_status_execution_state'] == 0:
            self.discard()
            return
        if p['i_rstb'] is None: return
        if b['o_body_flush']:
            self.discard()
            return
        if b['o_body_start']:
            if self.was_complete:assert self.completion_seen==1
            self.completion_seen=0
            self.was_complete=False
        if b['context_change']:
            assert not self.operations and all(not q for q in self.outputs), 'Live activation'
            cid=b['o_body_context_id']
            self.ctx=self.active['contexts'][cid].copy()
            assert pack(c.parameters,self.ctx)==b['o_body_context_image'], 'Mixed package image'
            if self.ctx['invalidate']:self.model.reset()
            coverage.hit('activation')
        width, m = c.SHELL_DATA_WIDTH, c.DATA_METADATA_WIDTH
        for port in range(2):
            if p['i_data_in_valid'] >> port & p['o_data_in_ready'] >> port & 1:
                data=(p['i_data_in_payload'] >> (port*width) & ((1 << width)-1)
                      if p['i_data_in_payload'] is not None else None)
                meta=p['i_data_in_metadata'] >> (port*m) & ((1 << m)-1)
                self.inputs[port].append((data,meta))
                coverage.counts['input_transfers']+=1
        if p['i_predicate_in_valid'] and p['o_predicate_in_ready']:
            self.predicates.append(p['i_predicate_in_payload'])
        if b['issue']:
            ctx=self.ctx
            assert ctx is not None
            operands={port:self.inputs[port].popleft() for port in required(ctx)}
            meta=next(iter(operands.values()))[1] if operands else b['o_body_context_id'] | b['o_body_context_version'] << c.aliases['CI']
            predicate=ctx['predicate_mode']==0 or ctx['predicate_mode']==1 and bool(self.predicates.popleft())
            self.operations.append(dict(ctx=ctx.copy(),inputs=operands,predicate=predicate,
                metadata=meta,tag=b['issued_tag'],cycle=self.cycles))
            coverage.counts['consumed_inputs']+=len(operands)
            coverage.counts['issued']+=1
        if b['commit']:
            assert self.operations, 'Retired unreserved work'
            op=self.operations.popleft()
            assert op['tag']==b['retired_tag'], 'Retirement reordered or duplicated'
            expected=self.model.evaluate(op['ctx'],op['inputs'],op['predicate'],op['metadata'])
            for key,signal in [('data','result'),('flags','result_flags'),('count','result_count'),
                               ('empty','result_empty'),('suppress','result_suppress')]:
                assert expected[key]==b[signal], (key,expected[key],b[signal],op['ctx']['operation'],op['ctx']['opcode'],op)
            latency=self.cycles-op['cycle']
            assert latency>=3, ('Premature retirement',latency)
            coverage.latencies.setdefault(str(op['ctx']['operation']),set()).add(latency)
            ctx=op['ctx']
            assert b['write_rf']==int(op['predicate'] and not expected['flags']&1 and ctx['write_rf'])
            meta=op['metadata']
            meta=(meta & ~(1 << (c.aliases['CI']+c.CONTEXT_VERSION_WIDTH))) | int(not op['predicate']) << (c.aliases['CI']+c.CONTEXT_VERSION_WIDTH)
            for value,offset,bits in ((ctx['operation'],64,8),(ctx['quality'],72,2),
                (ctx['model'],80,32),(expected['flags'],112,16),(expected['count'],128,16),
                (int(expected['empty']),144,1),(ctx['result_format'],152,8)):
                meta=(meta & ~(((1 << bits)-1) << offset)) | value << offset
            if not expected['suppress']:
                for port in range(c.DATA_OUTPUT_PORTS):
                    if ctx['output_mask'] >> port & 1:
                        self.outputs[port].append((expected['data'],meta))
                        coverage.counts['expected_copies']+=1
            coverage.counts['committed']+=1
            coverage.hit(f'operation_{ctx["operation"]}')
            if b['write_rf']:coverage.hit('write_rf')
            if b['write_acc']:coverage.hit('write_accumulator')
            if ctx['operation']==9:coverage.hit(f'accumulator_{ctx["opcode"]}')
            if not op['predicate']:coverage.hit('false_token' if ctx['false_token'] else 'false_suppress')
            if ctx['operation']==7:
                phase=op['metadata'] >> 32 & 7 if ctx['dynamic_phase'] else ctx['phase']
                coverage.hit(f'reduction_phase_{phase}')
                coverage.hit(f'reduction_{ctx["reduction"]}')
                if expected['empty']:coverage.hit('empty_reduction')
            if expected['flags']&8:coverage.hit('saturation')
            if expected['flags']&1:coverage.hit('exception_result')
            if ctx['operation'] in (4,5):coverage.hit(f'quality_{ctx["quality"]}')
            if ctx['operation']==6:coverage.hit(f'exp_base_{ctx["base"]}')
            if ctx['operation']==2 and expected['flags']&32:coverage.hit('lut_interpolation')
        for port in range(c.DATA_OUTPUT_PORTS):
            key=f'output_{port}'
            valid=p['o_data_out_valid'] >> port & 1
            ready=p['i_data_out_ready'] is not None and p['i_data_out_ready'] >> port & 1
            payload=(p['o_data_out_payload'] >> (port*width) & ((1 << width)-1),
                     p['o_data_out_metadata'] >> (port*m) & ((1 << m)-1))
            if key in self.holds:
                assert valid and payload==self.holds[key], 'Stalled output changed'
            if valid and not ready:self.holds[key]=payload;coverage.hit('backpressure')
            else:self.holds.pop(key,None)
            if valid and ready:
                assert self.outputs[port], 'Output without committed owner'
                assert payload==self.outputs[port].popleft(), ('output',port,payload)
                self.active.setdefault('observed',[]).append((port,*payload))
                coverage.counts['delivered']+=1
                coverage.hit('atomic_destinations')
        if p['o_event_out_valid'] and p['i_event_out_ready']:
            payload=p['o_event_out_payload']
            if payload&7==0:
                self.completion_seen+=1
                assert self.completion_seen==1, 'Duplicate completion event'
                assert payload >> (c.aliases['CI']+3)==p['o_status_kernel_id']
                assert payload >> 3 & ((1 << c.aliases['CI'])-1)==p['o_status_active_context']
                coverage.hit('completion_event')
        self.was_complete |= p['o_status_execution_state']==11
        if b['i_body_completed']:
            assert b['issued_tag']==self.ctx['steps'], 'Terminal issue count mismatch'
            assert not self.operations and all(not q for q in self.inputs), 'Premature completion'
            coverage.hit('ordered_completion')
        if b['fatal_now'] and obs.item.fault:coverage.hit('fault_containment')

    def check_phase(self):
        assert not self.operations and all(not q for q in self.outputs), 'Missing terminal effects'
        counts=self.coverage.counts
        assert counts['issued']==counts['committed']+counts['cancelled_operations']
        assert counts['input_transfers']==counts['consumed_inputs']+counts['cancelled_inputs']
        assert counts['expected_copies']==counts['delivered']+counts['cancelled_copies']
        self.coverage.cycles=self.cycles
