"""Check exact products, transaction deadlines, isolated inputs and every bank."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from multiplier.model import MultiplierModel, known, predict
from multiplier.transaction import Activity, INPUTS, OUTPUTS

PAYLOAD = ('o_product', 'o_product_signed', 'o_zero', 'o_negative')


class MultiplierScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = MultiplierModel(self.c)
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def prediction(self, ports):
        if self.c.latency and (ports['i_rstb'] != '1' or ports['i_clock_enable'] != '1'):
            return None
        return predict(self.c, ports)

    def isolation(self, obs):
        c, p, values = self.c, obs.ports, obs.internals
        prediction = self.prediction(p)
        event = prediction[1] if prediction else None
        active = event is not None and event['kind'] == 'valid'
        for name in ('a', 'b'):
            expected = p['i_operand_' + name] if active else '0' * c.operand
            assert values['isolated_' + name] == expected, f'Multiplier operand isolation: {name}'
            assert values['signed_' + name] == (p['i_signed_' + name] if active else '0')
        product = event['product'] % (1 << c.product_width) if active else 0
        assert values['product'] == bits(product, c.product_width), 'Exact full-width product'
        self.coverage.isolation_checks += 1

    def storage(self, obs):
        c, pre = self.c, obs.item.pre
        p, before, after = pre.ports, pre.internals, obs.internals
        enabled = obs.item.edge and p['i_rstb'] == p['i_clock_enable'] == '1'
        prediction = self.prediction(p)
        response, event = prediction if prediction else (None, None)
        for index in range(c.latency):
            control, data = f'control:{index}', f'storage:{index}'
            incoming_valid = p['i_valid'] if index == 0 else before[f'control:{index - 1}']
            reset = p['i_rstb'] == '0' and (obs.item.edge or c.asynchronous)
            expected_valid = '0' if reset else incoming_valid if enabled else before[control]
            assert after[control] == expected_valid, f'Pipeline valid enable/reset: {index}'
            capture = enabled and incoming_valid == '1'
            if capture:
                expected_data = (''.join(response[name] for name in PAYLOAD) if index == 0 else
                                 before[f'storage:{index - 1}'])
            else:
                expected_data = before[data]
            assert after[data] == expected_data, f'Pipeline data enable: {index}'
            self.coverage.storage_checks += 1
            self.coverage.stage_states.add((index, int(after[control])))
            if not enabled and not reset:
                self.coverage.frozen_states.add((index, int(after[control])))

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
            assert all(p[name] == item.pre.ports[name] for name in OUTPUTS), 'Pre-NBA sampling'
        if stage == 'post':
            event = self.model.step(item.pre.ports, item.edge)
            if event['kind'] == 'reset' and hasattr(item, 'reset_occupancy'):
                event['occupancy'] = item.reset_occupancy
            self.coverage.record(event, item)
            self.coverage.accounting = dict(
                accepted=self.model.accepted, emitted=self.model.emitted,
                reset_discarded=self.model.discarded)
            if c.check_internals and c.latency:
                self.storage(obs)
        if self.model.initialized:
            expected = self.model.output(p)
            for name in OUTPUTS:
                assert p[name] == expected[name], (
                    f'Multiplier {name}: {p[name]} != {expected[name]}'
                    f' ({item.get_name()}, {stage})')
            if c.check_internals and stage != 'edge':
                self.isolation(obs)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.model.initialized and not self.model.pending
        assert self.model.visible['o_valid'] == '0'
        assert self.model.accepted == self.model.emitted + self.model.discarded
        self.coverage.accounting = dict(
            accepted=self.model.accepted, emitted=self.model.emitted,
            reset_discarded=self.model.discarded)
