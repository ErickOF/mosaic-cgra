"""LevelShifter scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from level_shifter.model import expected_data
from level_shifter.transaction import Observation, OutputActivity


class LevelShifterScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.stable_input, (
                f"Output changed with stable source data: {observation.value}"
            )
            self.coverage.output_transitions += 1
            return
        assert isinstance(observation, Observation)
        assert observation.source == observation.requested, f"{observation.label}: source data was coerced"
        expected = expected_data(observation.source)
        assert observation.output == expected, (
            f"{observation.label}/{observation.stage}: source={observation.source}, "
            f"output={observation.output}, expected={expected}"
        )
        self.coverage.sample(observation)
