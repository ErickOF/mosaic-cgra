"""Check enabled-edge history, exact products, isolation and data-bank enables."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from dot_product.model import DotProductModel, element, known, predict
from dot_product.transaction import Activity, INPUTS, OUTPUTS

PAYLOAD = ('o_result', 'o_active_count', 'o_carry', 'o_overflow', 'o_saturated',
           'o_zero', 'o_negative')


class DotProductScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = DotProductModel(self.c)
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def input_prediction(self, ports):
        if self.c.latency and (ports['i_rstb'] != '1' or ports['i_clock_enable'] != '1'):
            return None
        return predict(self.c, ports)

    def isolation(self, obs):
        c, p, internal = self.c, obs.ports, obs.internals
        prediction = self.input_prediction(p)
        event = prediction[1] if prediction else None
        legal = event is not None and event['kind'] == 'legal'
        work = self.model.events[0] if c.latency >= 2 else event
        work_legal = work is not None and work['kind'] == 'legal'
        for k in range(c.terms):
            active = legal and bool(event['mask'] & (1 << k))
            for operand in ('a', 'b'):
                expected = element(p['i_operand_' + operand], k, c.element) if active else '0' * c.element
                assert internal[f'term:{k}:isolated_{operand}'] == expected, f'Multiplier isolation {k}'
            product = work['products'][k] if work_legal else 0
            assert internal[f'term:{k}:product'] == bits(product % (1 << (2 * c.element)),
                                                       2 * c.element), f'Exact product {k}'
        if c.accumulate:
            enabled = work_legal and bool(work['modes'][1])
            expected_dot = work['dot'] % (1 << c.width) if enabled else 0
            expected_acc = (work['total'] - work['dot']) % (1 << c.width) if enabled else 0
            assert internal['isolated_dot'] == bits(expected_dot, c.width), 'Pure dot adder isolation'
            assert internal['isolated_accumulator'] == bits(expected_acc, c.width), 'Accumulator isolation'
        self.coverage.isolation_checks += 1

    def storage(self, obs, previous):
        c, p = self.c, obs.item.pre.ports
        prediction = self.input_prediction(p)
        response, event = prediction if prediction else (None, None)
        legal = event is not None and event['kind'] == 'legal'
        enabled = obs.item.edge and p['i_rstb'] == p['i_clock_enable'] == '1'
        for name, value in obs.internals.items():
            if not name.startswith('storage:'):
                continue
            allowed = False
            expected = None
            if name.startswith('storage:response:'):
                index = int(name.split(':')[-1]) + int(c.latency >= 2)
                incoming = response if index == 0 else previous[index - 1]
                allowed = enabled and incoming is not None and incoming['o_valid'] == '1' and incoming['o_illegal_operation'] == '0'
                if allowed:
                    expected = ''.join(incoming[field] for field in PAYLOAD)
            elif name.startswith('storage:product:'):
                index = int(name.split(':')[-1])
                allowed = enabled and legal and bool(event['mask'] & (1 << index))
                if allowed:
                    expected = bits(event['products'][index] % (1 << (2 * c.element)), 2 * c.element)
            else:
                allowed = enabled and legal
                field = name.removeprefix('storage:work_')
                if field == 'accumulator':
                    allowed = allowed and p['i_accumulate'] == '1'
                if allowed:
                    expected = p['i_term_mask' if field == 'mask' else 'i_' + field]
            if allowed:
                assert value == expected, f'Pipeline capture: {name}: {value} != {expected}'
            else:
                assert value == obs.item.pre.internals[name], f'Pipeline data hold: {name}'
            self.coverage.storage_checks += 1

    def write(self, obs):
        if isinstance(obs, Activity):
            assert not self.model.initialized, f'Between-edge pipeline change: {obs.name}'
            return
        c, p, item, stage = self.c, obs.ports, obs.item, obs.stage
        for name in INPUTS:
            assert p[name] == item.ports[name], f'Stimulus coerced: {name}'
        if c.latency:
            assert known(p['i_rstb']), 'Protocol assertion failed: i_rstb'
            if p['i_rstb'] == '1':
                assert known(p['i_clock_enable']), 'Protocol assertion failed: i_clock_enable'
                if p['i_clock_enable'] == '1':
                    assert known(p['i_valid']), 'Protocol assertion failed: i_valid'
        if stage == 'pre' and c.latency and c.asynchronous and p['i_rstb'] == '0':
            item.reset_occupancy = self.model.occupancy
            self.model.reset()
        if stage == 'edge' and c.latency:
            assert item.pre is not None
            assert all(p[name] == item.pre.ports[name] for name in OUTPUTS), 'Pre-NBA sampling'
        if stage == 'post':
            previous = list(self.model.history)
            event = self.model.step(item.pre.ports, item.edge)
            if event['kind'] == 'reset' and hasattr(item, 'reset_occupancy'):
                event['occupancy'] = item.reset_occupancy
            self.coverage.record(event, item)
            self.coverage.accounting = dict(accepted=self.model.accepted, emitted=self.model.emitted,
                                            reset_discarded=self.model.discarded)
            if c.check_internals and c.latency:
                self.storage(obs, previous)
        if self.model.initialized:
            expected = self.model.output(p)
            for name in OUTPUTS:
                assert p[name] == expected[name], (f'Dot-product {name}: {p[name]} != {expected[name]}'
                                                  f' ({item.get_name()}, {stage})')
            if c.check_internals and stage != 'edge':
                self.isolation(obs)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.model.initialized
        assert not any(word['o_valid'] == '1' for word in self.model.history)
        assert self.model.accepted == self.model.emitted + self.model.discarded
        self.coverage.accounting = dict(accepted=self.model.accepted, emitted=self.model.emitted,
                                        reset_discarded=self.model.discarded)
