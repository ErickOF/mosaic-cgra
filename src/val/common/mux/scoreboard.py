"""Mux scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from mux.model import expected_outputs
from mux.transaction import OutputActivity


class MuxScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.quiet, (
                f"Unselected/stable input activity changed {observation.signal} to {observation.value}"
            )
            self.coverage.activity[observation.signal] += 1
            return
        config = self.config
        assert observation.packed_data == observation.requested.packed_data(config), "Data stimulus was coerced"
        assert observation.select == bits(observation.requested.select, config.select_width), "Selection was coerced"
        expected = expected_outputs(config, observation.packed_data, observation.select)
        assert (observation.output, observation.valid) == expected, (
            f"{observation.label}/{observation.stage}: select={observation.select}, "
            f"outputs={(observation.output, observation.valid)}, expected={expected}"
        )
        assert observation.valid in ("0", "1"), "Selection-valid must be known"
        self.coverage.sample(observation)
