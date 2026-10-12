"""IsolationCell scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from isolation_cell.model import expected_data
from isolation_cell.transaction import Observation, OutputActivity


class IsolationCellScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.continuously_isolated, (
                f"Source activity changed an isolated output to {observation.value}"
            )
            self.coverage.output_transitions += 1
            return
        assert isinstance(observation, Observation)
        config = self.config
        assert observation.isolate == str(observation.requested.isolate).lower(), "Isolation control was coerced"
        assert observation.data == observation.requested.data_bits(config.width), "Source data was coerced"
        illegal = observation.isolate if observation.isolate not in ("0", "1") else None
        assert illegal == observation.expected_unknown, (
            f"{observation.label}: known-control assertion {illegal}, expected {observation.expected_unknown}"
        )
        if illegal:
            if illegal not in self.coverage.control_unknowns:
                self.logger.info("Expected known-control assertion: i_isolate=%s", illegal)
            self.coverage.control_unknowns.add(illegal)
            self.coverage.control_violations += 1
        expected = expected_data(observation.data, observation.isolate, config.clamp_bits, config.active_high)
        assert observation.output == expected, (
            f"{observation.label}: control={observation.isolate}, data={observation.data}, "
            f"output={observation.output}, expected={expected}"
        )
        self.coverage.sample(observation)
