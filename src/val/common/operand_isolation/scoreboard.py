"""OperandIsolation scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from operand_isolation.model import expected_data
from operand_isolation.transaction import OutputActivity


class OperandIsolationScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.quiet, f"Isolated/stable input activity changed o_data to {observation.value}"
            self.coverage.output_transitions += 1
            return
        config = self.config
        assert observation.data == bits(observation.requested.data, config.width), "Data stimulus was coerced"
        assert observation.isolate == bits(observation.requested.isolate, 1), "Control stimulus was coerced"
        # Expected negative stimulus acknowledges a real assertion violation.
        # Untagged X/Z controls remain fatal; the runner proves this separately.
        try:
            assert observation.isolate in ("0", "1"), f"Known-control assertion failed: i_isolate={observation.isolate}"
        except AssertionError:
            if observation.expected_unknown != observation.isolate:
                raise
            if observation.stage == "settled":
                if not self.coverage.control_violations[observation.isolate]:
                    self.logger.info("Expected known-control assertion: i_isolate=%s", observation.isolate)
                self.coverage.control_violations[observation.isolate] += 1
        else:
            assert observation.expected_unknown is None, "Expected an unknown control but received a known value"
        expected = expected_data(observation.data, observation.isolate, config.clamp_bits)
        assert observation.output == expected, (
            f"{observation.label}/{observation.stage}: control={observation.isolate}, "
            f"data={observation.data}, output={observation.output}, expected={expected}"
        )
        self.coverage.sample(observation)
