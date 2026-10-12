"""LaneMask scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from lane_mask.constants import OUTPUTS
from lane_mask.model import expected_outputs, unknown_controls


class LaneMaskScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def write(self, observation):
        config = self.config
        ports, outputs = observation.ports, observation.outputs
        assert ports == observation.requested.ports(config.lanes), "A driven control was coerced"
        illegal = unknown_controls(ports)
        assert illegal == observation.expected_unknown, (
            f"{observation.label}: known-control assertions {illegal}, expected {observation.expected_unknown}"
        )
        for name in illegal:
            if not self.coverage.control_violations[name]:
                self.logger.info("Expected known-control assertion: %s contains X/Z", name)
            self.coverage.control_violations[name] += 1
        expected = expected_outputs(ports)
        for name, actual, reference in zip(OUTPUTS, outputs, expected, strict=True):
            assert actual == reference, f"{observation.label}: {ports}, {name}={actual}, expected {reference}"
        active, isolate, write = outputs
        assert isolate == active.translate(str.maketrans("01x", "10x")), "Isolation differs from canonical activity"
        assert write == active, "Write mask differs from canonical activity"
        assert all(set(word) <= set("01x") for word in outputs), "A derived control became high impedance"
        if ports[0] == "0":
            assert outputs == ("0" * config.lanes, "1" * config.lanes, "0" * config.lanes)
        self.coverage.sample(observation)
