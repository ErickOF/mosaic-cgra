"""Check combinational behavior, atomic edge transfers and live interface rules."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits, logic
from stream_join.model import StreamJoinModel, expected_outputs, known, lane, required_inputs
from stream_join.transaction import Activity, INPUTS


class StreamJoinScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = StreamJoinModel(self.config)
        self.locked_mask = self.blocked_output = self.retired = None
        self.producers = {}

    def protocol(self, ports, item):
        c = self.config
        assert not c.masked or known(ports['i_required']), 'Protocol assertion failed: i_required'
        selected = required_inputs(c, ports)
        unknown = [k for k in selected if ports['i_valid'][-k-1] not in '01']
        if unknown and all(ports['i_valid'][-k-1] == '1' for k in selected-set(unknown)):
            assert logic(cocotb.top.o_valid) == 'x', 'Required-valid uncertainty propagation assertion failed'
        assert not unknown, 'Protocol assertion failed: i_valid'
        missing = {k for k in selected if ports['i_valid'][-k-1] == '0'}
        # With at least two missing operands no ready can assert. Empty masks
        # also ignore downstream X/Z ready; otherwise it affects a ready cone.
        assert not selected or len(missing) >= 2 or known(ports['i_ready']), 'Protocol assertion failed: i_ready'
        if item is self.retired:
            return
        mask = bits(sum(1 << k for k in selected), c.inputs)
        assert self.locked_mask is None or mask == self.locked_mask, 'Protocol assertion failed: mask_stability'
        for k, data in self.producers.items():
            assert ports['i_valid'][-k-1] == '1' and lane(ports['i_data'], k, c.width) == data, 'Protocol assertion failed: producer_stability'
        if self.blocked_output is not None:
            assert (logic(cocotb.top.o_valid), logic(cocotb.top.o_data), logic(cocotb.top.o_required)) == self.blocked_output, 'Stalled-output stability assertion failed'
        if selected-missing:
            self.locked_mask = mask
        for k in selected-missing:
            if logic(cocotb.top.o_ready)[-k-1] == '0':
                self.producers.setdefault(k, lane(ports['i_data'], k, c.width))
        if logic(cocotb.top.o_valid) == '1' and ports['i_ready'] == '0':
            self.blocked_output = ('1', logic(cocotb.top.o_data), logic(cocotb.top.o_required))

    def write(self, observation):
        if isinstance(observation, Activity):
            ports = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
            self.protocol(ports, self.active['item'])
            assert not observation.forbidden, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        self.protocol(ports, item)
        for name, expected in expected_outputs(self.config, ports).items():
            assert ports[name] == expected, f'Stream-join assertion failed: {name}: {ports[name]} != {expected} ({item.get_name()}, {stage})'
        if stage == 'pre':
            self.coverage.arrivals(ports)
        if stage == 'edge':
            assert item.edge and item.pre is not None
            assert ports == item.pre.ports, 'Sampling-edge ordering assertion failed'
            accepted, joined = self.model.sample_edge(ports, item.four_state_data)
            self.coverage.edge(ports, accepted, joined, item.random)
            if joined:
                self.locked_mask = self.blocked_output = None
                self.producers.clear()
                self.retired = item
        self.coverage.observe(observation)
        self.coverage.ledger = dict(joined=self.model.joined, accepted=self.model.accepted,
            pending=[len(queue) for queue in self.model.queues])

    def check_phase(self):
        assert self.locked_mask is None and not self.producers and self.blocked_output is None, 'Regression left an active operation'
        assert all(not queue for queue in self.model.queues), 'Regression left accepted operands unmatched'
