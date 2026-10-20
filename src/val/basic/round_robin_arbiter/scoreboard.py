"""Compare all outputs/state, sampled fault recovery and payload ownership."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from round_robin_arbiter.model import ArbiterModel, known, payload
from round_robin_arbiter.transaction import Activity


class ArbiterScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.active = ConfigDB().get(self, '', 'active')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = ArbiterModel(self.config)

    def protocol(self, ports):
        violation = self.model.unknown_violation(ports)
        assert violation is None, f'Protocol assertion failed: {violation}'
        if self.config.fixture and self.model.initialized and ports['i_rstb'] == '1' and ports['i_flush'] == '0':
            if self.model.pending:
                index = self.model.pending[0]
                self.active['pulse_owner'] = index
                assert payload(ports, index) == self.model.pending_payload, 'Protocol assertion failed: pending_payload'

    def check_outputs(self, ports):
        for name, expected in self.model.outputs(ports).items():
            assert ports[name] == expected, f'Arbiter output assertion failed: {name}: {ports[name]} != {expected}'

    def write(self, observation):
        c, model = self.config, self.model
        if isinstance(observation, Activity):
            ports = {name: logic(getattr(cocotb.top, name)) for name in c.widths}
            # Check unknown-selection propagation before its expected rejection.
            if model.initialized and not self.active['edge_window'] and model.unknown_violation(ports) not in ('i_rstb', 'i_flush', 'i_accept'):
                self.check_outputs(ports)
            self.protocol(ports)
            assert not observation.forbidden, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in c.inputs:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        for name in ('i_rstb', 'i_flush', 'i_accept'):
            assert known(ports[name]), f'Protocol assertion failed: {name}'
        if stage == 'pre':
            item.start_class = model.state_class
            item.pointer_before = model.order[0]
            if c.asynchronous and ports['i_rstb'] == '0': model.reset()
            if not item.edge and (ports['i_rstb'] == '0' or ports['i_flush'] == '1'):
                self.coverage.pulses.add(('reset' if ports['i_rstb'] == '0' else 'flush', item.start_class))
        if stage == 'edge':
            assert item.pre is not None
            for name in c.outputs:
                assert ports[name] == item.pre.ports[name], f'Accepted-edge ordering assertion failed: {name}'
        if stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
                self.coverage.clears.add(('reset' if ports['i_rstb'] == '0' else 'flush', item.start_class))
                model.reset()
                self.coverage.boundary()
            else:
                assert model.initialized, 'Reset is required before traffic'
                self.protocol(ports)
                event = model.step(ports)
                if event['accepted']:
                    assert item.pre.ports['o_grant_accepted'] == '1' and int(item.pre.ports['o_grant_index'], 2) == event['winner'], 'Accepted requester assertion failed'
                    if c.fixture:
                        assert known(payload(ports, event['winner'])), 'Protocol assertion failed: accepted_payload'
                self.coverage.record(event, ports, model)
        if model.initialized:
            self.check_outputs(ports)
            self.protocol(ports)
            if c.check_internals:
                for name, expected in model.internals().items():
                    assert observation.internals[name] == expected, f'Arbiter state assertion failed: {name}: {observation.internals[name]} != {expected}'
        else:
            self.protocol(ports)
        self.coverage.observe(observation)

    def check_phase(self):
        assert self.model.pending is None and self.model.owner is None and not self.model.error, 'Regression left unfinished ownership or error'
