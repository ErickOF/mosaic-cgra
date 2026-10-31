"""Check accepted tokens, independent arithmetic, atomic commits and conservation."""
from pyuvm import ConfigDB, uvm_subscriber
from bct.model import Architecture, arithmetic, unpack, pack


def number(value):
    if isinstance(value, int):
        return value
    return int(value, 2) if value and set(value) <= {'0', '1'} else None


class BctScoreboard(uvm_subscriber):
    def build_phase(self):
        super().build_phase()
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = Architecture(self.c.parameters)
        self.tick = 0
        self.holds = {}

    def write(self, obs):
        if obs.domain != 'core':
            return
        p = {n: number(v) for n, v in obs.ports.items()}
        b = {n: number(v) for n, v in obs.body.items()}
        self.tick += 1
        m, c = self.model, self.c
        if p['i_rstb'] == 0 or p['o_status_execution_state'] == 0 or p['o_status_power_state'] == 4:
            self.discard()
            m.reset()
            self.holds.clear()
            return
        if b['o_body_flush'] and not p['o_body_isolate']:
            self.discard()
            m.reset()
            self.holds.clear()
            return
        if b['context_change']:
            cid = b['o_body_context_id']
            assert cid in self.active['contexts'], f'Unprogrammed context {cid}'
            image = self.active['contexts'][cid]
            assert image == b['o_body_context_image'], 'Activated context image differs from programmed image'
            assert not m.operations, 'Context change with pending operations'
            m.activate(unpack(c.parameters, image))
            self.coverage.hit('activation')
        if b['queue_count'] and not b['commit']:
            self.coverage.hit('backpressure')
        dmask = (1 << c.DATA_WIDTH) - 1
        mmask = (1 << c.DATA_METADATA_WIDTH) - 1
        for port in range(c.DATA_INPUT_PORTS):
            if p['i_data_in_valid'] >> port & p['o_data_in_ready'] >> port & 1:
                payload = p['i_data_in_payload'] >> (port * c.DATA_WIDTH) & dmask
                metadata = p['i_data_in_metadata'] >> (port * c.DATA_METADATA_WIDTH) & mmask
                m.inputs[port].append((payload, metadata))
                self.coverage.counts['accepted_inputs'] += 1
                self.coverage.hit(f'input_{port}')
        if p['i_predicate_in_valid'] and p['o_predicate_in_ready']:
            m.predicates.append(p['i_predicate_in_payload'])
        for op in m.operations:
            op['uncongested'] &= p['i_data_out_ready'] == (1 << c.DATA_OUTPUT_PORTS) - 1
        if b['issue']:
            ctx = m.context
            assert ctx is not None
            assert pack(c.parameters, ctx) == b['o_body_context_image'], 'Corrupt context issued'
            use_a = ctx['fu'] != 0 or ctx['opcode'] != 17 and (ctx['opcode'] != 15 or ctx['select_condition'])
            use_b = ctx['fu'] != 0 or ctx['opcode'] not in (5, 16) and (ctx['opcode'] != 15 or not ctx['select_condition'])
            indices = [ctx['source_a']] if use_a else []
            if use_b: indices.append(ctx['source_b'])
            if ctx['fu'] == 2: indices.append(ctx['source_c'])
            required = sorted(set(index for index in indices if index < c.DATA_INPUT_PORTS))
            a = m.source(ctx['source_a'], ctx) if use_a else 0
            right = m.source(ctx['source_b'], ctx) if use_b else 0
            acc = m.source(ctx['source_c'], ctx) if ctx['fu'] == 2 else 0
            assert not use_a or b['a'] == a, ('operand_a', b['a'], a)
            assert not use_b or b['b'] == right, ('operand_b', b['b'], right)
            assert ctx['fu'] != 2 or b['c'] == acc
            mode = ctx['predicate_mode']
            predicate = 1 if mode == 0 else m.predicates.popleft() if mode == 1 else m.pred[ctx['predicate_read']] if mode == 2 else 0
            predicate ^= ctx['predicate_invert']
            metadata = m.inputs[required[0]][0][1] if required else (
                b['o_body_context_version'] << c.aliases['CI'] | b['o_body_context_id'])
            value, flags = arithmetic(c.parameters, ctx, a, right, acc, predicate)
            if not predicate:
                value = 0
                metadata |= 1 << (c.aliases['CI'] + c.CONTEXT_VERSION_WIDTH)
            for index in required:
                m.inputs[index].popleft()
                self.coverage.counts['consumed_inputs'] += 1
            latency = (c.ALU_LATENCY, c.MULTIPLY_LATENCY, c.MAC_LATENCY)[ctx['fu']]
            from bct.model import sources
            if c.REGISTER_BYPASS and sources(c.parameters)['bypass'] in indices:
                latency += 1
            assert b['latency'] == latency
            operation = dict(data=value, metadata=metadata, predicate=flags[ctx['flag_select']] if ctx['flag_select'] < 7 else 0,
                ctx=ctx.copy(), true=predicate, tick=self.tick, latency=latency,
                first=not m.operations, uncongested=p['i_data_out_ready'] == (1 << c.DATA_OUTPUT_PORTS) - 1)
            m.operations.append(operation)
            self.coverage.hit(f'fu_{ctx["fu"]}')
            if ctx['fu'] == 0:
                self.coverage.hit(f'opcode_{ctx["opcode"]}')
            self.coverage.hit(f'predicate_{mode}')
            if not predicate:
                self.coverage.hit('false_token' if ctx['false_token'] else 'false_suppress')
            self.coverage.counts['issues'] += 1
        if b['commit']:
            assert m.operations, 'Commit without an independently predicted issue'
            op = m.operations.popleft()
            ctx, true = op['ctx'], op['true']
            assert b['commit_data'] == op['data'], ('result', b['commit_data'], op)
            assert self.tick - op['tick'] >= op['latency'] + 1, 'Result committed before advertised latency'
            if op['first'] and op['uncongested']:
                assert self.tick - op['tick'] == op['latency'] + 1, ('latency', op, self.tick)
                self.coverage.hit('exact_latency')
            assert b['commit_rf_enable'] == bool(true and ctx['write_rf'])
            assert b['commit_predicate_enable'] == bool(true and ctx['write_predicate'])
            assert b['commit_accumulator_enable'] == bool(true and ctx['write_accumulator'])
            assert b['commit_bypass_enable'] == bool(true and ctx['write_bypass'])
            if true:
                if ctx['write_rf']: m.rf[ctx['rf_write']] = op['data']
                if ctx['write_predicate']: m.pred[ctx['predicate_write']] = op['predicate']
                if ctx['write_accumulator']: m.acc[ctx['accumulator_write']] = op['data']
                if ctx['write_bypass']: m.bypass = op['data']
                m.previous = op['data']
            mask = ctx['output_mask'] if true or ctx['false_token'] else 0
            assert b['i_body_data_out_valid'] == mask, 'Partial destination commit'
            for port in range(c.DATA_OUTPUT_PORTS):
                if mask >> port & 1:
                    m.outputs[port].append((op['data'], op['metadata']))
                    self.coverage.hit(f'output_{port}')
            if true and ctx['predicate_output']:
                m.predicate_outputs.append(op['predicate'])
            self.coverage.counts['commits'] += 1
            for name in ('rf', 'predicate', 'accumulator', 'bypass'):
                if true and ctx[f'write_{name}']:
                    self.coverage.hit(f'write_{name}')
        for port in range(c.DATA_OUTPUT_PORTS):
            if p['o_data_out_valid'] >> port & p['i_data_out_ready'] >> port & 1:
                assert m.outputs[port], f'Unowned external output {port}'
                expected = m.outputs[port].popleft()
                actual = (p['o_data_out_payload'] >> (port * c.DATA_WIDTH) & dmask,
                          p['o_data_out_metadata'] >> (port * c.DATA_METADATA_WIDTH) & mmask)
                assert actual == expected, ('external_output', port, actual, expected)
                self.coverage.counts['outputs'] += 1
        if p['o_predicate_out_valid'] and p['i_predicate_out_ready']:
            assert m.predicate_outputs
            assert p['o_predicate_out_payload'] == m.predicate_outputs.popleft()
        for group in ('data', 'predicate', 'event'):
            valid = p[f'o_{group}_out_valid']
            ready = p[f'i_{group}_out_ready']
            count = getattr(c, group.upper() + '_OUTPUT_PORTS')
            width = getattr(c, group.upper() + '_WIDTH')
            for port in range(count):
                key = group, port
                payload = p[f'o_{group}_out_payload']
                data = None if payload is None else payload >> (port * width) & ((1 << width) - 1)
                if key in self.holds:
                    assert valid >> port & 1 and data == self.holds[key], f'Unstable output {key}'
                if valid >> port & 1 and not ready >> port & 1:
                    self.holds[key] = data
                    self.coverage.hit('backpressure')
                else:
                    self.holds.pop(key, None)

    def discard(self):
        self.coverage.counts['discarded_operations'] += len(self.model.operations)
        self.coverage.counts['discarded_inputs'] += sum(map(len, self.model.inputs))
        self.coverage.counts['discarded_outputs'] += sum(map(len, self.model.outputs))

    def check_phase(self):
        counts = self.coverage.counts
        assert counts['issues'] == counts['commits'] + counts['discarded_operations']
        assert counts['accepted_inputs'] == counts['consumed_inputs'] + counts['discarded_inputs']
        assert not self.model.operations and not any(self.model.inputs) and not any(self.model.outputs)
