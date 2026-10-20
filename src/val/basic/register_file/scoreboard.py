"""Check independent storage predictions, edge ordering and live access rules."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from register_file.model import RegisterFileModel, read_violation, write_violation
from register_file.transaction import Activity, INPUTS, fields


class RegisterFileScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = RegisterFileModel(self.config)

    def write(self, observation):
        if isinstance(observation, Activity):
            assert not observation.forbidden, f'Storage/held-output activity assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        config, model = self.config, self.model
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        if config.check_internals and model.raw is None:
            # Only a hold baseline for unspecified power-up contents. Functional
            # predictions remain unknown until an independently modeled write.
            model.raw = list(observation.storage)
        if stage == 'edge':
            assert item.edge and item.pre is not None
            assert ports['o_read_data'] == item.pre.ports['o_read_data'], 'Read-before-write edge assertion failed'
        if stage == 'post' and item.edge:
            self.coverage.record_writes(observation, model)
            model.step(ports)
        for r, (actual, expected) in enumerate(zip(fields(ports['o_read_data'], config.width), model.reads(ports))):
            if expected is not None:
                assert actual == expected, f'Read-data assertion failed: port {r}, {stage}, {item.get_name()}: {actual} != {expected}'
        if config.check_internals:
            for address, (actual, expected) in enumerate(zip(observation.storage, model.raw)):
                if expected is not None:
                    assert actual == expected, f'Storage update/hold assertion failed: entry {address}, {stage}'
        # Illegal read outputs are checked before rejection. Invalid write
        # addresses reach a real edge and a full state-preservation check first.
        violation = read_violation(config, ports)
        assert violation is None, f'Protocol assertion failed: {violation}'
        if stage == 'post' and item.edge:
            violation = write_violation(config, ports, item.four_state_data)
            assert violation is None, f'Protocol assertion failed: {violation}'
        self.coverage.sample(observation, model)

    def check_phase(self):
        assert all(word is not None for word in self.model.words), 'Regression left entries uninitialized'
