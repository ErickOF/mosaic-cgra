"""Check full beats, numerical invariants, stream obligations and state enables."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from packer.model import PackerModel, isolated_input, protocol_violation, split_elements
from packer.transaction import Activity, FIELDS, FRAME_INPUTS, INPUTS, OUTPUTS


class PackerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = PackerModel(self.config)
        self.input_hold = self.output_hold = None

    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.quiet:
                ports = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
                violation = protocol_violation(self.config, ports)
                assert violation is None, f'Protocol assertion failed: {violation}'
            assert not observation.quiet, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        violation = protocol_violation(self.config, ports)
        assert violation is None, f'Protocol assertion failed: {violation}'
        event = None
        if stage == 'pre':
            if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
                self.input_hold = self.output_hold = None
            else:
                if self.input_hold is not None:
                    assert tuple(ports[name] for name in FRAME_INPUTS) == self.input_hold, 'Protocol assertion failed: input_stability'
                if self.output_hold is not None:
                    assert ports['o_valid'] == '1' and tuple(ports[name] for name in FIELDS) == self.output_hold, 'Output-stability assertion failed'
            if ports['i_rstb'] == '0' and self.config.asynchronous:
                self.coverage.cancellations.add(('reset', int(bool(self.model.queue))))
                self.model.cancel(reset=True)
            if not item.edge and (ports['i_rstb'] == '0' or ports['i_flush'] == '1'):
                self.coverage.pulses.add('reset' if ports['i_rstb'] == '0' else 'flush')
        elif stage == 'post' and item.edge:
            pre = item.pre.ports
            if ports['i_rstb'] == '1' and ports['i_flush'] == '0' and pre['o_valid'] == '1' and ports['i_ready'] == '1' and self.config.registered:
                assert self.model.queue and all(pre[name] == self.model.queue[0][name] for name in FIELDS), 'Consumed-beat ordering assertion failed'
            event = self.model.step(ports)
            self.coverage.record(item, event, self.model)
            self.input_hold = (tuple(ports[name] for name in FRAME_INPUTS) if ports['i_valid'] == '1' and
                pre['o_ready'] == '0' and ports['i_rstb'] == '1' and ports['i_flush'] == '0' else None)
            self.output_hold = (tuple(pre[name] for name in FIELDS) if pre['o_valid'] == '1' and ports['i_ready'] == '0' and
                ports['i_rstb'] == '1' and ports['i_flush'] == '0' else None)

        expected = self.model.outputs(ports)
        for name in OUTPUTS:
            assert ports[name] == expected[name], f'Packer assertion failed: {name}: {ports[name]} != {expected[name]} ({item.get_name()}, {stage})'
        if ports['o_valid'] == '1':
            for word, valid, overflow, saturated in zip(split_elements(ports['o_data'], self.config.destination_width),
                    reversed(ports['o_lane_valid']), reversed(ports['o_overflow']), reversed(ports['o_saturated'])):
                assert valid == '1' or (int(word, 2) == 0 and overflow == saturated == '0'), 'Invalid-lane clamping assertion failed'
                assert saturated == '0' or overflow == '1', 'Saturation implies overflow assertion failed'
            assert ports['o_any_overflow'] == str(int('1' in ports['o_overflow'])), 'Aggregate overflow assertion failed'
            assert ports['o_any_saturated'] == str(int('1' in ports['o_saturated'])), 'Aggregate saturation assertion failed'
        if self.config.check_internals:
            assert observation.internals['isolated_data'] == isolated_input(self.config, ports), 'Input-isolation assertion failed'
            if self.config.registered and self.model.initialized:
                assert observation.internals['stored_result'] == self.model.storage, 'Payload-storage assertion failed'
                assert observation.internals['stored_valid'] == str(int(bool(self.model.queue))), 'Validity-storage assertion failed'
        self.coverage.checks[stage] += 1

    def check_phase(self):
        assert not self.model.queue and self.input_hold is None, 'Pending stream obligations were not drained'
        assert self.model.accepted == self.model.consumed + self.model.cancelled, 'Final beat conservation assertion failed'
