"""Check atomic numerical updates, independent response timing and live legality."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits, logic
from accumulator.model import AccumulatorModel, known, lane
from accumulator.transaction import Activity, INPUTS, OUTPUTS, RAW


class AccumulatorScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = AccumulatorModel(self.config)

    def protocol(self, ports):
        for name in ('i_rstb', 'i_clock_enable'):
            assert known(ports[name]), f'Protocol assertion failed: {name}'
        if ports['i_rstb'] == ports['i_clock_enable'] == '1':
            assert known(ports['i_valid']), 'Protocol assertion failed: i_valid'
            if ports['i_valid'] == '1' and not self.model.causes(ports) and ports['i_command'] != '00':
                for k in self.model.selected(ports):
                    assert known(lane(ports['i_data'], k, self.config.width)), 'Protocol assertion failed: active_data'

    def isolated(self, ports, internals):
        if not self.config.check_internals or not self.model.initialized:
            return
        c = self.config
        selected = self.model.selected(ports)
        for k in range(c.lanes):
            for op, code in (('add', '10'), ('sub', '11')):
                if op == 'sub' and not c.subtract:
                    continue
                active = k in selected and ports['i_command'] == code
                left = self.model.values[k] if active else 0
                right = lane(ports['i_data'], k, c.width) if active else '0'*c.width
                assert internals[f'{op}_left[{k}]'] == bits(left, c.width), f'Arithmetic isolation assertion failed: {op}_left[{k}]'
                assert internals[f'{op}_right[{k}]'] == right, f'Arithmetic isolation assertion failed: {op}_right[{k}]'

    def write(self, observation):
        c, model = self.config, self.model
        if isinstance(observation, Activity):
            ports = {name:logic(getattr(cocotb.top, name)) for name in INPUTS}
            self.protocol(ports)
            assert not observation.forbidden_bits, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item, stage = observation.ports, observation.item, observation.stage
        self.protocol(ports)
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        if c.check_internals and not model.raw:
            model.raw = {name:observation.internals[name] for name in RAW}
        if stage == 'pre':
            item.population_before = sum(value is not None for value in model.values)
            if c.asynchronous and ports['i_rstb'] == '0':
                model.reset()
            if not item.edge and ports['i_rstb'] == '0':
                self.coverage.reset_pulses.add(item.population_before)
            self.active['selected'] = model.selected(ports)
        if stage == 'edge':
            assert item.edge and item.pre is not None
            for name in OUTPUTS:
                assert ports[name] == item.pre.ports[name], f'Edge-ordering assertion failed: {name}'
        if stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            event = model.step(item.pre.ports)
            self.coverage.record(event, item.pre.ports, item)
        if model.initialized:
            for name, expected in model.outputs().items():
                assert ports[name] == expected, f'Accumulator assertion failed: {name}: {ports[name]} != {expected} ({item.get_name()}, {stage})'
            if c.check_internals:
                for name, expected in model.raw.items():
                    assert observation.internals[name] == expected, f'Storage write-enable assertion failed: {name}'
            self.isolated(ports, observation.internals)
        self.coverage.observe(observation)
        self.coverage.ledger = dict(accepted=model.accepted, legal=model.legal, illegal=model.illegal,
            bubbles=model.bubbles, stalls=model.stalls, updates=model.updates)

    def check_phase(self):
        assert self.model.initialized and self.model.accepted == self.model.legal+self.model.illegal
