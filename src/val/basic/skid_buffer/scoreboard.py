"""Check queue ordering, zero-cycle bypass, capture-only writes and producer holds."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from skid_buffer.model import SkidBufferModel, known
from skid_buffer.transaction import Activity, CONTROLS, INPUTS, OUTPUTS


class SkidBufferScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.active = ConfigDB().get(self, '', 'active')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = SkidBufferModel(self.config)
        self.pending = None

    def protocol(self, ports):
        for name in CONTROLS:
            assert known(ports[name]), f'Protocol assertion failed: {name}'
        if ports['i_rstb'] == '0':
            self.pending = None
        elif self.pending is not None:
            assert ports['i_valid'] == '1' and ports['i_data'] == self.pending, 'Protocol assertion failed: producer_stability'

    def outputs(self, ports):
        for name, expected in self.model.outputs(ports).items():
            assert ports[name] == expected, f'Skid-buffer assertion failed: {name}: {ports[name]} != {expected}'

    def write(self, observation):
        if isinstance(observation, Activity):
            ports = {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)}
            self.protocol(ports)
            if self.config.asynchronous and ports['i_rstb'] == '0':
                self.outputs(ports)
            assert not observation.forbidden, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        c, model = self.config, self.model
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        self.protocol(ports)
        if c.check_internals and model.raw_data is None:
            # This is a hold baseline, never an architectural power-up value.
            model.raw_data = observation.internals['buffer_data']
        if stage == 'pre':
            item.start_count = len(model.queue)
            if c.asynchronous and ports['i_rstb'] == '0':
                self.coverage.reset_epoch()
                model.reset()
            if model.initialized and ports['i_rstb'] == '1' and ports['i_valid'] == '1' and model.outputs(ports)['o_ready'] == '0':
                self.pending = ports['i_data']
            if not item.edge and ports['i_rstb'] == '0':
                self.coverage.reset_pulses.add(item.start_count)
        if stage == 'edge':
            assert item.edge and item.pre is not None
            for name in OUTPUTS:
                assert ports[name] == item.pre.ports[name], f'Consumer edge-ordering assertion failed: {name}'
        if stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            if ports['i_rstb'] == '0':
                model.edge += 1
                self.coverage.reset_cases.add((item.start_count, int(ports['i_valid']), int(ports['i_ready'])))
                self.coverage.reset_epoch()
                model.reset()
            else:
                assert model.initialized, 'A reset is required before traffic'
                event = model.step(ports)
                if event['pop']:
                    assert item.pre.ports['o_valid'] == '1' and item.pre.ports['o_data'] == event['consumed'], 'Consumed-token ordering assertion failed'
                if event['push']:
                    assert item.pre.ports['o_ready'] == '1', 'Input acceptance while full assertion failed'
                    self.pending = None
                    assert item.four_state_data or known(ports['i_data']), 'Protocol assertion failed: accepted_data'
                self.coverage.record(event, ports)
        if model.initialized:
            self.outputs(ports)
            if c.check_internals:
                assert observation.internals['buffer_valid'] == str(int(bool(model.queue))), 'Stored-valid assertion failed'
                assert observation.internals['buffer_data'] == model.raw_data, 'Payload capture-enable assertion failed'
            model.conservation()
            self.active['occupied'] = bool(model.queue)
            self.coverage.ledger = dict(accepted=model.accepted, consumed=model.consumed,
                discarded=model.discarded, pending=len(model.queue))
        self.coverage.observe(observation)

    def check_phase(self):
        self.model.conservation()
        assert not self.model.queue and self.pending is None, 'Regression left a pending token'
