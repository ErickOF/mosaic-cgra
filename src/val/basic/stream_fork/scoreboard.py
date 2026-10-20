"""Check independent deliveries, reset timing, storage enables and producer rules."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from stream_fork.model import StreamForkModel, known, lane
from stream_fork.transaction import Activity, INPUTS, OUTPUTS


class StreamForkScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = StreamForkModel(self.config)
        self.offer = None

    def protocol(self, ports):
        for name in ('i_rstb', 'i_valid'):
            assert known(ports[name]), f'Protocol assertion failed: {name}'
        if ports['i_rstb'] == '0':
            self.offer = None
            return
        if ports['i_valid'] == '1' and self.config.masked:
            assert known(ports['i_destination']), 'Protocol assertion failed: i_destination'
            assert int(ports['i_destination'], 2) != 0, 'Protocol assertion failed: zero_destination'
        # Ready of an unselected/completed destination is deliberately ignored.
        valid = logic(cocotb.top.o_valid)
        for k, state in enumerate(reversed(ports['i_ready'])):
            if valid[-k-1] == '1':
                assert state in '01', 'Protocol assertion failed: i_ready'
        if self.offer is not None:
            assert ports['i_valid'] == '1' and self.offer == self.offer_value(ports), 'Protocol assertion failed: producer_stability'

    def offer_value(self, ports):
        return (ports['i_data'], ports['i_destination'] if self.config.masked else None)

    def write(self, observation):
        c, model = self.config, self.model
        if isinstance(observation, Activity):
            ports = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
            self.protocol(ports)
            if c.asynchronous and ports['i_rstb'] == '0':
                assert logic(cocotb.top.o_valid) == '0'*c.outputs and logic(cocotb.top.o_data) == '0'*(c.width*c.outputs) and logic(cocotb.top.o_ready) == '1', 'Asynchronous reset assertion failed'
            assert not observation.forbidden, f'Quiet-waveform assertion failed: {observation.name}'
            if ports['i_rstb'] == '1':
                for k, data in self.active.get('held_lanes', {}).items():
                    assert logic(cocotb.top.o_valid)[-k-1] == '1' and lane(logic(cocotb.top.o_data), k, c.width) == data, 'Stalled-output stability assertion failed'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        self.protocol(ports)
        if c.check_internals and model.raw_data is None:
            model.raw_data = observation.internals['fork_data']
        if stage == 'pre':
            item.start_count = model.pending.bit_count()
            if c.asynchronous and ports['i_rstb'] == '0':
                self.coverage.reset_epoch()
                model.reset()
            if model.initialized and ports['i_rstb'] == '1' and ports['i_valid'] == '1' and model.outputs(ports)['o_ready'] == '0':
                self.offer = self.offer_value(ports)
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
                self.coverage.reset_populations.add(item.start_count)
                self.coverage.reset_epoch()
                model.reset()
            else:
                assert model.initialized, 'A reset is required before traffic'
                event = model.step(item.pre.ports)
                if event['push']:
                    self.offer = None
                    assert item.four_state_data or known(ports['i_data']), 'Protocol assertion failed: accepted_data'
                self.coverage.record(event, item.pre.ports)
        if model.initialized:
            for name, expected in model.outputs(ports).items():
                assert ports[name] == expected, f'Stream-fork assertion failed: {name}: {ports[name]} != {expected} ({item.get_name()}, {stage})'
            if c.check_internals:
                assert observation.internals['pending'] == model.outputs(ports)['o_valid'], 'Stored-pending assertion failed'
                assert observation.internals['fork_data'] == model.raw_data, 'Payload write-enable assertion failed'
            model.conservation()
            self.coverage.ledger = model.ledger()
        self.coverage.observe(observation)

    def check_phase(self):
        self.model.conservation()
        assert self.model.pending == 0 and self.offer is None, 'Regression left a pending copy or producer'
