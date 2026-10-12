"""PriorityEncoder scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from priority_encoder.model import expected_outputs
from priority_encoder.transaction import OutputActivity


class PriorityEncoderScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


    def assert_known_consistency(self, observation, reference):
        """Check interface invariants separately from the reference tuple."""
        request = int(observation.request, 2)
        valid, index, onehot, multiple = (int(value, 2) for value in observation.outputs)
        assert valid == bool(request), "Valid does not match request reduction"
        assert onehot.bit_count() <= 1, "Onehot0 assertion failed"
        assert onehot & ~request == 0, "Granted request does not exist"
        assert multiple == (request.bit_count() > 1), "Multiple indication is incorrect"
        if valid:
            assert onehot.bit_count() == 1 and 0 <= index < self.config.width
            assert onehot == 1 << index and request & onehot
            assert all(not self.config.higher(other, index) for other in reference.known), "Higher-priority request was bypassed"
        else:
            assert index == onehot == multiple == 0, "No-request outputs retained stale state"

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.quiet, f"Stable request changed {observation.signal} to {observation.value}"
            self.coverage.activity[observation.signal] += 1
            return
        config = self.config
        assert observation.request == bits(observation.requested, config.width), "Request stimulus was coerced"
        reference = expected_outputs(config, observation.request)
        # Deliberate ambiguous requests acknowledge a live assertion failure;
        # untagged ambiguity is fatal and is proven by separate X/Z probes.
        try:
            assert not reference.ambiguous, f"Ambiguous-request assertion failed: i_request={observation.request}"
        except AssertionError:
            if not observation.expected_ambiguity:
                raise
            if observation.stage == "settled":
                if not self.coverage.ambiguity_violations:
                    self.logger.info("Expected ambiguous-request assertion: i_request=%s", observation.request)
                self.coverage.ambiguity_violations += 1
        else:
            assert not observation.expected_ambiguity, "Expected ambiguous request was not ambiguous"
        assert observation.outputs == reference.outputs, (
            f"{observation.label}/{observation.stage}: request={observation.request}, "
            f"outputs={observation.outputs}, expected={reference.outputs}"
        )
        if not reference.unknown:
            self.assert_known_consistency(observation, reference)
        self.coverage.sample((observation, reference))
