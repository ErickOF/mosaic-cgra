"""Check byte mapping, complete frames, stream obligations and storage activity."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from data_aligner.model import AlignerModel, isolated_window, protocol_violation
from data_aligner.transaction import Activity, FRAME_INPUTS, INPUTS, OUTPUTS


class AlignerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = AlignerModel(self.config)
        self.input_hold = None

    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.quiet:
                # An unknown asynchronous reset can poison storage before the
                # next scheduled sample. Diagnose its cause before its effects.
                ports = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
                violation = protocol_violation(ports)
                assert violation is None, f'Protocol assertion failed: {violation}'
            assert not observation.quiet, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item = observation.ports, observation.item
        for name in INPUTS:
            if name != 'i_clk' or observation.stage != 'pre':
                assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        violation = protocol_violation(ports)
        assert violation is None, f'Protocol assertion failed: {violation}'
        if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
            self.input_hold = None
        elif self.input_hold is not None:
            assert tuple(ports[name] for name in FRAME_INPUTS) == self.input_hold, 'Protocol assertion failed: input_stability'
        before = self.model.outputs(ports)
        event = self.model.step(ports)
        if event['rising']:
            self.input_hold = (tuple(ports[name] for name in FRAME_INPUTS)
                               if ports['i_valid'] == '1' and before['o_ready'] == '0' and
                               ports['i_rstb'] == '1' and ports['i_flush'] == '0' else None)
        expected = self.model.outputs(ports)
        for name in OUTPUTS:
            assert ports[name] == expected[name], (
                f'Aligner assertion failed: {item.get_name()}/{observation.stage}: '
                f'{name}={ports[name]}, expected={expected[name]}')
        if self.config.check_internals:
            assert observation.internals['isolated_data'] == isolated_window(self.config, ports), 'Input-isolation assertion failed'
            if self.config.registered and self.model.initialized:
                assert observation.internals['stored_result'] == self.model.storage, 'Payload-storage assertion failed'
                assert observation.internals['stored_valid'] == str(int(bool(self.model.queue))), 'Validity-storage assertion failed'
        self.coverage.sample(observation, event, self.model)
        self.coverage.totals = dict(accepted=self.model.accepted, consumed=self.model.consumed, cancelled=self.model.cancelled)

    def check_phase(self):
        assert not self.model.queue, 'Pending output obligations were not drained'
        assert self.input_hold is None, 'Producer ended with a stalled input'
        self.coverage.totals = dict(accepted=self.model.accepted, consumed=self.model.consumed, cancelled=self.model.cancelled)
