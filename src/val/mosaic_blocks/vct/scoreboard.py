"""Check public token ownership, independent vector results and atomic slice commits."""
from pyuvm import ConfigDB, uvm_subscriber
from bct.scoreboard import number
from vct.model import Architecture, compute, unpack, pack, operands_used, dimensions, lane_width


class VctScoreboard(uvm_subscriber):
    def build_phase(self):
        super().build_phase()
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = Architecture(self.c.parameters)
        self.tick = self.enabled = 0
        self.holds = {}

    def discard(self):
        m = self.model
        self.coverage.counts['discarded_operations'] += len(m.operations)
        self.coverage.counts['discarded_inputs'] += sum(map(len,m.inputs))
        self.coverage.counts['discarded_outputs'] += sum(map(len,m.outputs))

    def write(self, obs):
        if obs.domain != 'core': return
        p = {n: number(v) for n, v in obs.ports.items()}
        b = {n: number(v) for n, v in obs.body.items()}
        self.tick += 1
        self.enabled += bool(b['advance'])
        m, cfg = self.model, self.c
        if p['i_rstb'] == 0 or p['o_status_execution_state'] == 0 or p['o_status_power_state'] == 4:
            self.discard()
            m.reset()
            self.holds.clear()
            return
        if p['i_rstb'] is None:
            assert not b['issue'] and not b['commit'], 'Unknown reset allowed execution'
            return
        if b['o_body_flush'] and not p['o_body_isolate']:
            self.discard()
            m.reset()
            self.holds.clear()
            return
        if p['o_status_fatal_error']:
            self.discard()
            m.reset()
            self.holds.clear()
            return
        if b['context_change']:
            cid = b['o_body_context_id']
            assert cid in self.active['contexts']
            assert self.active['contexts'][cid] == b['o_body_context_image']
            assert not m.operations, 'Context changed with outstanding work'
            m.activate(unpack(cfg.parameters, self.active['contexts'][cid]))
            self.coverage.hit('activation')
        for port in range(cfg.DATA_INPUT_PORTS):
            if p['i_data_in_valid'] >> port & p['o_data_in_ready'] >> port & 1:
                data = p['i_data_in_payload']
                # Directed inactive-X tests may contain unknown lane bits. Preserve
                # each known bit; the independent mask excludes every unknown lane.
                if data is None:
                    raw = obs.ports['i_data_in_payload'].replace('X', '0').replace('Z', '0').replace('x','0').replace('z','0')
                    data = int(raw, 2)
                m.inputs[port].append((data >> (port * cfg.DATA_WIDTH) & ((1 << cfg.DATA_WIDTH) - 1),
                    p['i_data_in_metadata'] >> (port * cfg.DATA_METADATA_WIDTH) & ((1 << cfg.DATA_METADATA_WIDTH) - 1)))
                self.coverage.counts['accepted_inputs'] += 1
        if p['i_predicate_in_valid'] and p['o_predicate_in_ready']:
            m.predicates.append(p['i_predicate_in_payload'])
        if b['queue_count'] and not b['commit']: self.coverage.hit('backpressure')
        if b['issue']:
            c = m.context
            assert c is not None and pack(cfg.parameters, c) == b['o_body_context_image']
            assert not m.operations, 'Serialized issue contract violated'
            use = operands_used(c)
            indices = [c[f'source_{name}'] for name, enabled in zip('abc', use) if enabled]
            required = sorted(set(n for n in indices if n < cfg.DATA_INPUT_PORTS))
            metadata = m.inputs[required[0]][0][1] if required else 0
            base = cfg.aliases['CI'] + cfg.CONTEXT_VERSION_WIDTH
            full = (1 << cfg.NUM_LANES) - 1
            mask = c['lane_mask']
            if c['metadata_mask'] and required: mask &= metadata >> (base + 3) & full
            if c['tail_mask']:
                mask &= c['runtime_tail']
                if required: mask &= metadata >> (base + 4 + cfg.NUM_LANES) & full
            if c['local_mask']:
                assert m.mask_valid & mask == mask
                mask &= m.mask_value
            candidate = mask
            if c['predicate_mode'] == 0: predicate = full
            elif c['predicate_mode'] == 1:
                assert m.predicates, 'Unowned predicate token'
                predicate = m.predicates.popleft()
            elif c['predicate_mode'] == 2:
                state = m.pred[c['predicate_read']]
                assert all(l in state for l in range(cfg.NUM_LANES) if candidate >> l & 1)
                predicate = sum(v << l for l, v in state.items())
            else: predicate = 0
            if c['predicate_invert']: predicate ^= full
            mask &= predicate
            assert b['effective_mask'] == mask, ('mask', b['effective_mask'], mask)
            values = [m.source(c[f'source_{n}'], c, mask) if used else 0 for n, used in zip('abc', use)]
            data, pred, ov, sat = compute(cfg.parameters, c, *values, mask)
            for port in required:
                m.inputs[port].popleft()
                self.coverage.counts['consumed_inputs'] += 1
            latency = (cfg.LANE_LATENCY, cfg.REDUCTION_LATENCY, cfg.DOT_LATENCY, 0, 0, 0)[c['fu']]
            from vct.model import sources
            latency += bool(cfg.REGISTER_BYPASS and sources(cfg.parameters)['bypass'] in indices)
            assert b['latency'] == latency
            outmeta = b['o_body_context_version'] << cfg.aliases['CI'] | b['o_body_context_id']
            outmeta |= c['result_format'] << base | mask << (base + 3) | c['signed_mode'] << (base + 3 + cfg.NUM_LANES)
            m.operations.append(dict(data=data, pred=pred, mask=mask, metadata=outmeta, context=c.copy(),
                                     tick=self.tick, enabled=self.enabled, latency=latency))
            self.coverage.hit(f'fu_{c["fu"]}')
            self.coverage.hit(f'opcode_{c["opcode"]}' if c['fu'] == 0 else f'crossop_{c["fu"]}_{c["opcode"]}')
            self.coverage.hit(f'mask_{mask}')
            self.coverage.hit(f'format_{c["result_format"]}')
            self.coverage.hit(f'predicate_{c["predicate_mode"]}')
            if not mask: self.coverage.hit('false_token' if c['false_token'] else 'false_suppress')
            if sat: self.coverage.hit('saturation')
            self.coverage.counts['issues'] += 1
        if b['commit']:
            assert m.operations, 'Commit without issue'
            op = m.operations.popleft()
            c, mask, data = op['context'], op['mask'], op['data']
            assert b['commit_data'] == data, ('result', b['commit_data'], op)
            assert self.tick - op['tick'] >= op['latency'] + 1, 'Early result'
            if self.enabled - op['enabled'] == op['latency'] + 1: self.coverage.hit('exact_latency')
            dest = c['output_mask'] if mask or c['false_token'] else 0
            assert b['i_body_data_out_valid'] == dest, 'Partial multi-output commit'
            for port in range(cfg.DATA_OUTPUT_PORTS):
                if dest >> port & 1: m.outputs[port].append((data, op['metadata']))
            if c['predicate_output'] and mask: m.predicate_outputs.append(op['pred'])
            if mask and c['write_rf']:
                d = dimensions(cfg.parameters)
                width = lane_width(cfg.parameters, c['result_format'])
                expected_mask = newdata = 0
                for lane in range(cfg.NUM_LANES):
                    for s in range(width // cfg.WRITE_SLICE_WIDTH):
                        index = lane * d['SP'] + c['write_slice'] + s
                        if mask >> lane & 1 and (not c['slice_mask'] or c['slice_mask'] >> index & 1):
                            expected_mask |= 1 << index
                            bitpos = index * cfg.WRITE_SLICE_WIDTH
                            group = ((1 << cfg.WRITE_SLICE_WIDTH) - 1) << bitpos
                            value = data >> (lane * width + s * cfg.WRITE_SLICE_WIDTH) & ((1 << cfg.WRITE_SLICE_WIDTH) - 1)
                            m.rf[c['rf_write']] = (m.rf[c['rf_write']] & ~group) | value << bitpos
                            m.rf_valid[c['rf_write']] |= 1 << index
                assert b['write_mask'] == expected_mask, 'Incorrect VRF slice mask'
                self.coverage.hit('write_rf')
            if mask:
                if c['write_mask']:
                    m.mask_value = m.mask_value & ~mask | op['pred'] & mask
                    m.mask_valid |= mask
                if c['write_predicate']:
                    for lane in range(cfg.NUM_LANES):
                        if mask >> lane & 1: m.pred[c['predicate_write']][lane] = op['pred'] >> lane & 1
                    self.coverage.hit('write_predicate')
                if c['write_vacc']:
                    for lane in range(cfg.NUM_LANES):
                        if mask >> lane & 1: m.vacc[c['vacc_write']][lane] = data >> (lane * cfg.ACC_WIDTH) & ((1 << cfg.ACC_WIDTH) - 1)
                    self.coverage.hit('write_vacc')
                if c['write_sacc']:
                    m.sacc[c['sacc_write']] = data & ((1 << cfg.ACC_WIDTH) - 1)
                    self.coverage.hit('write_sacc')
                if c['write_bypass']:
                    merged = data
                    if m.bypass is not None and m.bypass_format == c['result_format'] < 3:
                        width = lane_width(cfg.parameters, c['result_format'])
                        for lane in range(cfg.NUM_LANES):
                            if not mask >> lane & 1:
                                lane_bits = ((1 << width) - 1) << (lane * width)
                                merged = merged & ~lane_bits | m.bypass & lane_bits
                    m.bypass = merged
                    m.bypass_format = c['result_format']
                    self.coverage.hit('write_bypass')
                m.previous = data
            self.coverage.counts['commits'] += 1
        for port in range(cfg.DATA_OUTPUT_PORTS):
            if p['o_data_out_valid'] >> port & 1:
                got = (p['o_data_out_payload'] >> (port * cfg.DATA_WIDTH) & ((1 << cfg.DATA_WIDTH) - 1),
                       p['o_data_out_metadata'] >> (port * cfg.DATA_METADATA_WIDTH) & ((1 << cfg.DATA_METADATA_WIDTH) - 1))
                if port in self.holds: assert got == self.holds[port], 'Output changed while stalled'
                ready = p['i_data_out_ready']
                if ready is None:
                    ready = int(obs.ports['i_data_out_ready'].lower().replace('x','0').replace('z','0'),2)
                if ready >> port & 1:
                    assert m.outputs[port], f'Unowned external output {port}'
                    assert got == m.outputs[port].popleft(), ('external output', got)
                    self.holds.pop(port, None)
                    self.coverage.counts['outputs'] += 1
                else: self.holds[port] = got
        if p['o_predicate_out_valid'] and p['i_predicate_out_ready']:
            assert m.predicate_outputs and p['o_predicate_out_payload'] == m.predicate_outputs.popleft()
        if p['o_status_execution_state'] == 11:
            assert not m.operations and not any(m.outputs) and not m.predicate_outputs, 'Premature completion'
