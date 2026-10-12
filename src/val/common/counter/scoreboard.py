"""Counter scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from counter.model import next_state
from counter.transaction import State


class CounterScoreboard(uvm_scoreboard):
    """Assert registered, combinational, reset, and legal-control behavior."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.state = State(self.config.reset_value)
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write

    def check_terminal(self, state, direction, terminal, label):
        expected = (
            int(state.count == (0 if direction else self.config.maximum))
            if direction in (0, 1) else 0
        )
        assert terminal == expected, f"{label}: terminal {terminal}, expected {expected}"

    def write(self, observation):
        mid = observation.mid_inputs
        edge = observation.edge_inputs
        invalid = mid.invalid_controls | edge.invalid_controls
        if invalid:
            # These are intentional negative tests of the known-control
            # assertions. Do not predict unspecified arithmetic from X/Z.
            assert invalid == {observation.expected_unknown}, (
                f"{observation.label}: unexpected unknown controls {invalid}"
            )
            for name in invalid:
                self.coverage.unknown_controls.add((name, getattr(mid, name)))
            if "direction" in invalid:
                assert observation.mid_terminal == observation.edge_terminal == 0, (
                    "Unknown direction must force terminal low"
                )
            self.state = None
            self.logger.info("Expected known-control assertion: %s", observation.label)
            return
        assert observation.expected_unknown is None, (
            "The simulator resolved an injected X/Z; four-state verification is required"
        )
        previous = self.state
        before_edge = (
            State(self.config.reset_value)
            if self.config.async_reset and mid.rstb == 0 else previous
        )
        if before_edge is not None:
            assert observation.mid_state == before_edge, (
                f"{observation.label}: mid-cycle state {observation.mid_state}, expected {before_edge}"
            )
            self.check_terminal(before_edge, mid.direction, observation.mid_terminal, observation.label)
        expected = next_state(self.config, before_edge, edge)
        assert observation.edge_state == expected, (
            f"{observation.label}: state {observation.edge_state}, expected {expected}; inputs={edge}"
        )
        assert not (expected.overflow and expected.underflow)
        self.check_terminal(expected, edge.direction, observation.edge_terminal, observation.label)
        self.coverage.sample(observation, previous, expected)
        self.state = expected
