"""Decoder scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from decoder.model import expected_outputs
from decoder.transaction import Observation, OutputActivity


class DecoderScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.continuously_disabled, (
                f"Disabled selection activity changed {observation.signal} to {observation.value}"
            )
            assert not set(observation.value) - {"0", "1"}, "An output became unknown"
            if observation.signal == "o_decoded":
                value = int(observation.value, 2)
                assert value & (value - 1) == 0, "A transient decoded value was multi-hot"
            self.coverage.activity[observation.signal] += 1
            return
        assert isinstance(observation, Observation)
        config = self.config
        assert observation.enable == str(observation.requested.enable).lower(), "Enable stimulus was resolved or changed"
        assert observation.select == observation.requested.select_bits(config.select_width), "Selection stimulus was resolved or changed"
        assert not (set(observation.decoded + observation.valid) - {"0", "1"}), "Outputs must always be known"
        decoded, valid = int(observation.decoded, 2), int(observation.valid, 2)
        expected = expected_outputs(config.num_outputs, observation.enable, observation.select)
        assert (decoded, valid) == expected, (
            f"{observation.label}: enable={observation.enable}, select={observation.select}; "
            f"outputs={(decoded, valid)}, expected={expected}"
        )
        assert decoded & (decoded - 1) == 0, "o_decoded must be one-hot or zero"
        self.coverage.sample(observation)
