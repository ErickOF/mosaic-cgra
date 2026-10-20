"""Check independent slice writes/holds, edge-time old reads and access legality."""

import cocotb
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import logic
from vector_register_file.model import VectorRegisterFileModel, read_violation, write_violation
from vector_register_file.transaction import Activity, INPUTS, fields


class VectorRegisterFileScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = VectorRegisterFileModel(self.config)

    def check_reads(self, ports, label):
        for index, (actual, expected) in enumerate(zip(fields(ports['o_read_data'], self.config.slice_width),
                self.model.reads(ports), strict=True)):
            if expected is not None:
                assert actual == expected, f'Read-data assertion failed: slice {index}, {label}: {actual} != {expected}'

    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.name.startswith('i_read_'):
                ports = {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, 'o_read_data')}
                self.check_reads(ports, 'live read controls')
                violation = read_violation(self.config, ports)
                assert violation is None, f'Protocol assertion failed: {violation}'
            else:
                assert not observation.forbidden, f'Storage/held-output activity assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        c, model = self.config, self.model
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        if c.check_internals and model.raw is None:
            # A hold baseline only; functional power-up data stays unspecified.
            model.raw = list(observation.storage)
        if stage == 'edge':
            assert item.edge and item.pre is not None
            assert ports['o_read_data'] == item.pre.ports['o_read_data'], 'Read-before-write edge assertion failed'
        if stage == 'post' and item.edge:
            self.coverage.record_writes(observation, model)
            model.step(ports)
        self.check_reads(ports, f'{item.get_name()}/{stage}')
        if c.check_internals:
            assert len(observation.storage) == c.depth*c.mask_width
            for index, (actual, expected) in enumerate(zip(observation.storage, model.raw, strict=True)):
                if expected is not None:
                    assert actual == expected, f'Slice storage update/hold assertion failed: entry {index//c.mask_width}, slice {index % c.mask_width}, {stage}'
        violation = read_violation(c, ports)
        assert violation is None, f'Protocol assertion failed: {violation}'
        if stage == 'post' and item.edge:
            # Invalid writes reach a real edge and check all unrelated state
            # before rejection. Overlap has no defined winning payload.
            violation = write_violation(c, ports, item.four_state_data)
            assert violation is None, f'Protocol assertion failed: {violation}'
        self.coverage.sample(observation, model)

    def check_phase(self):
        assert all(value is not None for entry in self.model.slices for value in entry), 'Regression left slices uninitialized'
