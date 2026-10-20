"""Check consumed selections, forwarding, independent captures, and waveform holds."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard

from bypass_network.model import ForwardingModel, requests, violations
from bypass_network.transaction import Activity, INPUTS, pack, unpack


class BypassNetworkScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.model = ForwardingModel(self.config)
        self.reported = set()

    def write(self, observation):
        if isinstance(observation, Activity):
            changed = sum(1 << bit for bit, (before, after) in enumerate(zip(reversed(observation.before), reversed(observation.after))) if before != after)
            assert not changed & observation.quiet_mask, f"Quiet-waveform assertion failed: {observation.signal}"
            self.coverage.transitions[observation.signal] += 1
            return
        config, item, ports = self.config, observation.item, observation.ports
        for name in INPUTS:
            if name != "i_clk" or observation.stage != "pre":
                assert ports[name] == item.ports[name], f"Stimulus was coerced: {name}"
        routes = requests(config, ports)
        found = violations(config, ports, routes)
        for violation in sorted(found):
            try:
                assert False, f"Protocol assertion failed: {violation}"
            except AssertionError:
                if violation not in item.violations:
                    raise
                if observation.stage == "pre":
                    self.coverage.violations[violation] += 1
                if violation not in self.reported:
                    self.logger.info("Expected protocol assertion: %s", violation)
                    self.reported.add(violation)
        assert found == item.violations, f"Expected violation did not occur: {item.violations - found}"
        old_valid = tuple(self.model.valid)
        rising = self.model.step(ports, routes)
        expected = self.model.outputs(routes)
        for index, name in enumerate(("o_destination_data", "o_destination_valid", "o_selection_error")):
            width = config.width if index == 0 else 1
            wanted = pack((values[index] for values in expected), width)
            assert ports[name] == wanted, f"Forwarding assertion failed: {item.get_name()}/{observation.stage}: {name}={ports[name]}, expected={wanted}"
        if config.check_internals:
            data = tuple(self.model.data) if config.registered else ("0" * config.width,) * config.destinations
            valid = tuple(self.model.valid) if config.registered else ("0",) * config.destinations
            assert observation.stored_data == data, "Registered-payload assertion failed: capture, hold, or unreset state"
            assert observation.stored_valid == valid, "Registered-validity assertion failed: capture, reset, or flush priority"
        self.coverage.sample(observation, routes, rising, old_valid)
