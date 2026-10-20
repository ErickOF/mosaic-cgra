"""Check live protocol, real handshakes, conservation and accepted-only storage."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits, logic
from width_converter.model import WidthConverterModel, known, lane
from width_converter.transaction import Activity, CONTROLS, INPUTS, OUTPUTS, PAYLOAD, STORAGE


class WidthConverterScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = WidthConverterModel(self.config)
        self.pending = None
        self.terminal = 0

    def protocol(self, ports):
        for name in CONTROLS:
            assert known(ports[name]), f'Protocol assertion failed: {name}'
        if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
            self.pending = None
            return
        if self.pending is not None:
            assert ports['i_valid'] == '1' and tuple(ports[name] for name in PAYLOAD) == self.pending, 'Protocol assertion failed: producer_stability'
        if ports['i_valid'] == '1':
            for k, keep in enumerate(reversed(ports['i_keep'])):
                if keep == '1':
                    assert known(lane(ports['i_data'], k, self.config.unit_width)), 'Protocol assertion failed: active_data'

    def accepted_protocol(self, ports):
        for name in ('i_keep', 'i_last', 'i_user'):
            assert known(ports[name]), f'Protocol assertion failed: {name}'

    def write(self, observation):
        c, model = self.config, self.model
        if isinstance(observation, Activity):
            ports = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
            self.protocol(ports)
            assert not observation.forbidden_bits, f'Quiet-waveform assertion failed: {observation.name}'
            if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
                for name in OUTPUTS:
                    assert logic(getattr(cocotb.top, name)) == '0'*c.widths[name], f'Cancellation clamp assertion failed: {name}'
            self.coverage.transitions[observation.name] += 1
            return
        ports, item, stage = observation.ports, observation.item, observation.stage
        self.protocol(ports)
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        if c.check_internals and not model.raw:
            model.raw = {name: observation.internals[name] for name in STORAGE}
        if stage == 'pre':
            item.state_before = self.coverage.state(model)
            item.position_before = model.position
            if c.asynchronous and ports['i_rstb'] == '0':
                model.reset()
                self.terminal = 0
            if model.initialized and ports['i_rstb'] == '1' and ports['i_flush'] == '0' and ports['i_valid'] == '1' and not model.ready(ports):
                self.pending = tuple(ports[name] for name in PAYLOAD)
            if not item.edge and ports['i_rstb'] == '0':
                self.coverage.reset_pulses.add(item.state_before)
        if stage == 'edge':
            assert item.edge and item.pre is not None
            if ports['i_rstb'] == '1' and ports['i_flush'] == '0' and ports['i_valid'] == ports['o_ready'] == '1':
                self.accepted_protocol(ports)
            for name in OUTPUTS:
                assert ports[name] == item.pre.ports[name], f'Consumer edge-ordering assertion failed: {name}'
        if stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
                self.coverage.cancel(item, ports)
                model.edge += 1
                model.reset()
                self.terminal = 0
            else:
                assert model.initialized, 'Reset is required before traffic'
                event = model.step(item.pre.ports)
                if event['push']:
                    self.pending = None
                    if c.mode == 'unpack':
                        self.terminal = event['terminal']
                self.coverage.record(event, item.pre.ports)
        if model.initialized:
            for name, expected in model.outputs(ports).items():
                assert ports[name] == expected, f'Width-converter assertion failed: {name}: {ports[name]} != {expected} ({item.get_name()}, {stage})'
            if c.check_internals:
                for name, expected in model.raw.items():
                    assert observation.internals[name] == expected, f'Storage write-enable assertion failed: {name}'
                assert observation.internals['valid'] == str(int(bool(model.queue))), 'Stored-valid assertion failed'
                if c.mode != 'equal':
                    width = max(1, (c.ratio-1).bit_length())
                    assert observation.internals['index'] == bits(model.position, width), 'Slice-index assertion failed'
                    if c.mode == 'unpack':
                        assert observation.internals['terminal'] == bits(self.terminal, width), 'Terminal-index assertion failed'
            model.conservation()
            self.coverage.ledger = model.ledger()
        self.active['position'] = model.position
        self.coverage.observe(observation)

    def check_phase(self):
        self.model.conservation()
        assert not self.model.busy and self.pending is None, 'Regression left pending stream state'
