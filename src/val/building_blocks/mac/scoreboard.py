"""Check arithmetic, enabled-edge deadlines, transaction conservation and activity."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from mac.model import MacModel, known, predict
from mac.transaction import Activity, INPUTS, OUTPUTS


class MacScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = MacModel(self.c)
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
        active = event is not None and event['kind'] == 'legal'
        for name in ('a', 'b'):
            expected = p['i_operand_' + name] if active else '0' * c.operand
            assert values['isolated_' + name] == expected, f'Multiplier operand isolation: {name}'
        if c.latency >= 2:
            work_legal = values['work_valid'] == '1' and values['work_illegal'] == '0'
            product = values['storage:product'] if work_legal else '0' * (2 * c.operand)
            accumulator = values['storage:work_accumulator'] if work_legal else '0' * c.width
            signed = work_legal and values['work_signed'] == '1'
        else:
            product = bits(event['product'] & ((1 << (2 * c.operand)) - 1),
                           2 * c.operand) if active else '0' * (2 * c.operand)
            accumulator = p['i_accumulator'] if active else '0' * c.width
            signed = active and p['i_signed'] == '1'
        assert values['product'] == product, 'Exact full-width product'
        extension = product[0] if signed else '0'
        assert values['isolated_dot'] == extension * (c.width - len(product)) + product
        assert values['isolated_accumulator'] == accumulator, 'Addend isolation'
        self.coverage.isolation_checks += 1

    def storage(self, obs):
        c, pre = self.c, obs.item.pre
        p, before = pre.ports, pre.internals
        prediction = self.prediction(p)
        event = prediction[1] if prediction else None
        enabled = obs.item.edge and p['i_rstb'] == p['i_clock_enable'] == '1'
        legal = event is not None and event['kind'] == 'legal'
        for name, value in obs.internals.items():
            if name.startswith('control:'):
                if p['i_rstb'] == '0' and (obs.item.edge or c.asynchronous):
                    assert value == '00', f'Reset dominance: {name}'
                elif not enabled:
                    assert value == before[name], f'Frozen valid/illegal state: {name}'
                self.coverage.storage_checks += 1
                continue
            if not name.startswith('storage:'):
                continue
            allowed, expected = enabled and legal, None
            if name.startswith('storage:response:'):
                index = int(name.split(':')[-1])
                valid = (before['work_valid'] if index == 0 else
                         before[f'control:response:{index - 1}'][0])
                illegal = (before['work_illegal'] if index == 0 else
                           before[f'control:response:{index - 1}'][1])
                allowed = enabled and valid == '1' and illegal == '0'
                expected = (before['payload'] if index == 0 else
                            before[f'storage:response:{index - 1}'])
            elif allowed:
                field = name.removeprefix('storage:work_')
                if name == 'storage:product':
                    expected = bits(event['product'] & ((1 << (2 * c.operand)) - 1), 2 * c.operand)
                else:
                    expected = '1' if field in ('mask', 'accumulate') else p['i_' + field]
            assert value == (expected if allowed else before[name]), f'Pipeline data enable: {name}'
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
                assert p[name] == expected[name], (f'MAC {name}: {p[name]} != {expected[name]}'
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
