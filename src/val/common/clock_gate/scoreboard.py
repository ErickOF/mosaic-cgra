"""ClockGate scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from clock_gate.constants import CONTROLS
from clock_gate.model import effective_enable
from clock_gate.transaction import OutputChange, Snapshot


class ClockGateScoreboard(uvm_scoreboard):
    """Derive the latch from ports only; never read an RTL internal node."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.latched = str(int(self.config.startup_enabled))
        self.expected_output = "0"


    def write(self, observation):
        if isinstance(observation, OutputChange):
            self.coverage.output_changes.append(observation)
            return
        assert isinstance(observation, Snapshot)
        self.coverage.snapshots += 1
        assert observation.clk in ("0", "1"), "Source clock must always be known"
        invalid = {name for name in CONTROLS if getattr(observation, name) not in ("0", "1")}
        if invalid:
            # Expected assertion failures exercise the illegal-control checker.
            # All other unknown controls terminate the test immediately.
            assert observation.expected_unknown is not None, f"Unexpected unknown controls: {invalid}"
            name, value = observation.expected_unknown
            assert invalid == {name} and getattr(observation, name) == value
            other = getattr(observation, CONTROLS[1 - CONTROLS.index(name)])
            diagnostic = (name, value, other, "low" if observation.clk == "0" else "high")
            if diagnostic not in self.coverage.unknown_controls:
                self.logger.info("Expected known-control assertion: %s", diagnostic)
            self.coverage.unknown_controls.add(diagnostic)
        else:
            self.coverage.combinations.add((observation.enable, observation.test_enable))

        if observation.clk == "0":
            self.latched = effective_enable(observation.enable, observation.test_enable)
        expected = "0" if observation.clk == "0" else self.latched
        assert observation.gclk == expected, (
            f"{observation.label} at {observation.time_ps} ps: o_gclk={observation.gclk}, "
            f"expected {expected}; clk={observation.clk}, captured enable={self.latched}"
        )
        if expected != self.expected_output:
            self.coverage.expected_changes.append((observation.time_ps, self.expected_output, expected))
        self.expected_output = expected

        previous = self.previous
        if previous is not None:
            phase = "low" if observation.clk == "0" else "high"
            for name in CONTROLS:
                before, after = getattr(previous, name), getattr(observation, name)
                if before != after and before in ("0", "1") and after in ("0", "1"):
                    self.coverage.half_cycle_transitions.add((name, after, phase))
                    self.coverage.requests.append({
                        "time_ps": observation.time_ps, "control": name,
                        "requested_value": after, "phase": phase,
                        "captured_enable": self.latched,
                    })
            if observation.clk != previous.clk:
                edge = "rise" if observation.clk == "1" else "fall"
                self.coverage.source_edges.append((observation.time_ps, edge))
                if edge == "rise":
                    self.coverage.decisions.append({
                        "time_ps": observation.time_ps, "captured_enable": self.latched,
                        "actual_output": observation.gclk,
                        "enable": observation.enable, "test_enable": observation.test_enable,
                        "label": observation.label,
                    })
        self.previous = observation
