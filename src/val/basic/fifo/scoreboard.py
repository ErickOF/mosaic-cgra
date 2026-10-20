"""Check ordering, ready/valid obligations, state enables and reset priority."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from fifo.model import FifoModel, protocol_violation
from fifo.transaction import Activity, INPUTS, OUTPUTS


class FifoScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = FifoModel(self.config)
        self.input_hold = self.output_hold = None
        self.memory = None
        self.reset_active = False

    def reset(self):
        if self.model.initialized:
            self.coverage.resets.add(len(self.model.queue))
            self.coverage.discarded += len(self.model.queue)
        self.model.reset()
        self.input_hold = self.output_hold = None
        self.coverage.input_stall = self.coverage.output_stall = self.coverage.stream = 0

    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.quiet:
                ports = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
                violation = protocol_violation(ports)
                assert violation is None, f'Protocol assertion failed: {violation}'
            assert not observation.quiet, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return

        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        violation = protocol_violation(ports)
        assert violation is None, f'Protocol assertion failed: {violation}'
        event = None
        if stage == 'pre':
            if ports['i_rstb'] == '0':
                if not item.edge:
                    self.coverage.between_edge_resets += 1
                self.input_hold = self.output_hold = None
                if self.config.asynchronous and not self.reset_active:
                    self.reset()
            else:
                if self.input_hold is not None:
                    assert (ports['i_valid'], ports['i_data']) == self.input_hold, 'Protocol assertion failed: input_stability'
                if self.output_hold is not None:
                    assert ports['o_valid'] == '1' and ports['o_data'] == self.output_hold, 'Output-stability assertion failed'
            self.reset_active = ports['i_rstb'] == '0'
        elif stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            if ports['i_rstb'] == '0':
                if not self.config.asynchronous:
                    self.reset()
            else:
                assert self.model.initialized, 'A reset edge is required before transactions'
                # Compare the actual consumed head before advancing the queue.
                pre = item.pre.ports
                if pre['o_valid'] == '1' and pre['i_ready'] == '1':
                    assert self.model.queue and pre['o_data'] == self.model.queue[0], 'Consumed-item ordering assertion failed'
                event = self.model.step(ports)
                if event['push'] and set(ports['i_data']) & set('xz'):
                    assert item.get_name() == 'intentional_four_state_payload', 'Protocol assertion failed: accepted_data'
                self.coverage.record(event, ports, len(self.model.queue))
                self.input_hold = ((ports['i_valid'], ports['i_data'])
                                   if ports['i_valid'] == '1' and pre['o_ready'] == '0' else None)
                self.output_hold = pre['o_data'] if pre['o_valid'] == '1' and ports['i_ready'] == '0' else None

        if self.model.initialized:
            assert 0 <= len(self.model.queue) <= self.config.depth, 'Occupancy range assertion failed'
            expected = self.model.outputs(ports)
            for name in OUTPUTS:
                assert ports[name] == expected[name], f'FIFO assertion failed: {name}: {ports[name]} != {expected[name]} ({item.get_name()}, {stage})'
            if self.config.check_internals:
                for name, value in (('read_pointer', self.model.read), ('write_pointer', self.model.write)):
                    assert int(observation.internals[name], 2) == value, f'Pointer assertion failed: {name}'
                    assert value < self.config.depth, f'Pointer range assertion failed: {name}'
        if self.config.check_internals:
            current = {name: value for name, value in observation.internals.items() if name.startswith('memory:')}
            if self.memory is not None:
                for name, value in current.items():
                    expected = (ports['i_data'] if event and event['push'] and name == f"memory:{event['write']}" else self.memory[name])
                    assert value == expected, f'Storage-enable assertion failed: {name}'
            self.memory = current
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert not self.model.queue, 'Regression did not drain all surviving items'
        assert self.coverage.accepted == self.coverage.consumed + self.coverage.discarded, 'Accepted-item conservation assertion failed'
