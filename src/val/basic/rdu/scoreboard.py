"""Check accepted-advance latency, raw storage enables and producer obligations."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from rdu.model import RduModel, fields, pack, protocol_violation
from rdu.transaction import Activity, INPUTS, OUTPUTS


class RduScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = RduModel(self.config)
        self.pending_bypass = {}
        self.raw_seeded = False

    def check_protocol(self, ports):
        violation = protocol_violation(self.config, ports)
        if violation == 'i_delay' and self.model.initialized:
            expected = self.model.outputs(ports)
            for name in OUTPUTS:
                assert logic(getattr(cocotb.top, name)) == expected[name], f'Unknown-delay propagation assertion failed: {name}'
        assert violation is None, f'Protocol assertion failed: {violation}'
        data = fields(ports['i_input_data'], self.config.width)
        delays = fields(ports['i_delay'], self.config.delay_width)
        for c, word in tuple(self.pending_bypass.items()):
            if ports['i_rstb'] == '0' or ports['i_flush'][-c-1] == '1':
                del self.pending_bypass[c]
            else:
                assert ports['i_channel_enable'][-c-1] == '1' and int(delays[c], 2) == 0 and \
                    ports['i_input_valid'][-c-1] == '1' and data[c] == word, 'Protocol assertion failed: bypass_stability'

    def reset(self, ports):
        if self.model.initialized:
            self.coverage.reset_occupancies.update((c, sum(token is not None for token in line)) for c, line in enumerate(self.model.history))
            self.coverage.boundaries.update(self.model.boundaries(ports))
        self.model.reset(ports)
        self.pending_bypass.clear()

    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.name in INPUTS:
                self.check_protocol({name: logic(getattr(cocotb.top, name)) for name in INPUTS})
            assert not observation.quiet_change, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        config, model = self.config, self.model
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        self.check_protocol(ports)
        if config.check_internals and not self.raw_seeded:
            model.raw_data = fields(observation.internals['delay_data'], config.width)
            self.raw_seeded = True
        if stage == 'pre':
            if model.initialized:
                boundaries = model.boundaries(ports)
                if item.edge:
                    self.coverage.boundaries.update(boundaries)
            if config.asynchronous and ports['i_rstb'] == '0':
                self.reset(ports)
            if not item.edge and ports['i_rstb'] == '0':
                self.coverage.reset_pulses += 1
        if stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            self.coverage.priority.add((int(ports['i_rstb']), int(int(ports['i_flush'], 2) != 0), int(ports['i_advance'])))
            if ports['i_rstb'] == '0':
                self.reset(ports)
            else:
                assert model.initialized, 'A reset edge is required before traffic'
                records = model.step(ports)
                # Transfers consume the pre-edge token, never the post-edge tap.
                for record in records:
                    c, consumed = record['channel'], record['consumed']
                    if item.pre.ports['o_output_transfer'][-c-1] == '1':
                        assert consumed is not None and fields(item.pre.ports['o_output_data'], config.width)[c] == consumed, 'Consumed-token ordering assertion failed'
                        self.pending_bypass.pop(c, None)
                    else:
                        assert consumed is None, 'Missing output-transfer assertion failed'
                self.coverage.record(records, ports, item.pre.ports)
        if stage == 'pre' and ports['i_rstb'] == '1' and ports['i_advance'] == '0':
            for c, delay in enumerate(fields(ports['i_delay'], config.delay_width)):
                if ports['i_channel_enable'][-c-1] == '1' and ports['i_flush'][-c-1] == '0' and int(delay, 2) == 0 and ports['i_input_valid'][-c-1] == '1':
                    self.pending_bypass[c] = fields(ports['i_input_data'], config.width)[c]
        if model.initialized:
            for name, expected in model.outputs(ports).items():
                assert ports[name] == expected, f'RDU assertion failed: {name}: {ports[name]} != {expected} ({item.get_name()}, {stage})'
            model.conservation()
            if config.check_internals:
                valid = [int(token is not None) for line in model.history for token in line] or [0]
                assert observation.internals['delay_valid'] == pack(valid, 1), 'Stage-validity assertion failed'
                assert observation.internals['delay_data'] == pack(model.raw_data, config.width), 'Payload-storage enable assertion failed'
            self.coverage.observe(observation, model)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        self.model.conservation()
        assert not any(token is not None for line in self.model.history for token in line), 'Regression did not drain surviving tokens'
        assert not self.pending_bypass, 'Regression left an unconsumed bypass operand'
