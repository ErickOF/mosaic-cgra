"""Check masked storage, validity lifecycle, protocol legality, and read timing."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from context_memory.model import ContextModel, protocol_violations
from context_memory.transaction import Activity, INPUTS, pack


class ContextMemoryScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.model = ContextModel(self.config)
        self.reported = set()

    def write(self, observation):
        if isinstance(observation, Activity):
            changed = sum(1 << bit for bit, (before, after) in enumerate(zip(reversed(observation.before), reversed(observation.after))) if before != after)
            assert not changed & observation.quiet_mask, f"Quiet-waveform assertion failed: {observation.signal}"
            self.coverage.transitions[observation.signal] += 1
            return
        ports, item, config = observation.ports, observation.item, self.config
        for name in INPUTS:
            if name != "i_clk" or observation.stage != "pre":
                assert ports[name] == item.ports[name], f"Stimulus was coerced: {name}"
        found = protocol_violations(config, ports)
        for violation in sorted(found | self.model.commit_violations(ports)):
            assert violation in item.violations, f"Protocol assertion failed: {violation}"
            if violation not in self.reported:
                self.logger.info("Expected protocol assertion: %s", violation)
                self.reported.add(violation)
            self.coverage.violations[violation] += observation.stage == "post"
        assert found == item.violations, f"Expected violation missing: {item.violations - found}"
        old_valid = tuple(self.model.valid)
        rising, active = self.model.step(ports)
        expected = self.model.reads(ports)
        for index, name in enumerate(OUTPUTS_FOR_CHECK):
            wanted = pack((values[index] for values in expected), config.width if index == 0 else 1)
            assert ports[name] == wanted, f"Read assertion failed: {item.get_name()}/{observation.stage}: {name}={ports[name]}, expected={wanted}"
        if config.check_internals:
            assert observation.data == tuple(self.model.data), "Context-storage assertion failed: masked write or unreset state"
            assert observation.valid == pack(self.model.valid, 1), "Context-validity assertion failed: commit, invalidation, or reset"
        self.coverage.sample(observation, active, rising, old_valid, tuple(self.model.valid))


OUTPUTS_FOR_CHECK = ("o_read_data", "o_read_valid")
