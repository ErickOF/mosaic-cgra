"""WriteGate scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from write_gate.constants import TRUTH
from write_gate.model import control_violations, decision
from write_gate.transaction import Activity


class WriteGateScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write


        self.register = "0" * self.config.width
        self.memory = [self.register] * 4
        self.pending = None


    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.signal in ("o_write_enable", "o_write_suppressed"):
                assert not observation.quiet, f"Stable controls changed {observation.signal} to {observation.value}"
                self.coverage.output_transitions += 1
            else:
                assert observation.capture_window and self.pending is not None, f"Destination changed outside capture: {observation.signal}"
                register, memory = self.pending
                expected = register if observation.signal == "o_register_state" else "".join(reversed(memory))
                assert observation.value == expected, f"Destination waveform mismatch: {observation.signal}"
            return
        item, config = observation.item, self.config
        assert observation.write == bits(item.inputs.write, config.width), "Write stimulus was coerced"
        assert observation.suppress == bits(item.inputs.suppress, config.width), "Suppression stimulus was coerced"
        violations = control_violations(observation.write, observation.suppress)
        try:
            assert not violations, f"Known-control assertion failed: {','.join(sorted(violations))}"
        except AssertionError:
            if violations != item.expected_violations:
                raise
            if observation.stage == "settled":
                self.coverage.violations.update(violations)
        else:
            assert not item.expected_violations, "Expected an illegal control but received legal controls"
        expected = [TRUTH[w, s] for w, s in zip(observation.write, observation.suppress, strict=True)]
        assert observation.permitted == "".join(row[0] for row in expected), f"Permitted-write mismatch: {item.get_name()}/{observation.stage}"
        assert observation.suppressed == "".join(row[1] for row in expected), f"Suppressed-write mismatch: {item.get_name()}/{observation.stage}"
        for w, s, p, b in zip(observation.write, observation.suppress, observation.permitted, observation.suppressed, strict=True):
            if w in "01" and s in "01":
                assert not (p == b == "1"), "Mutual-exclusion assertion failed"
                assert (p == "1" or b == "1") == (w == "1"), "Request-partition assertion failed"
        if config.integration:
            self.check_destination(observation)
        self.coverage.sample(observation)

    def check_destination(self, observation):
        """Compare all HDL state against ungated writes, including untouched words."""
        inputs = observation.item.inputs
        assert not control_violations(observation.write, observation.suppress), "Illegal controls cannot reach destination capture"
        assert observation.data == bits(inputs.data, self.config.width), "Data stimulus was coerced"
        assert observation.destination == (inputs.destination == "memory") and observation.address == inputs.address
        assert inputs.protocol in ("idle", "accepted", "cancelled")
        assert observation.valid == (inputs.protocol == "accepted")
        assert inputs.reason in ("none", "redundant_value", "inactive_destination")
        if inputs.protocol == "idle":
            assert observation.write.count("1") == 0
        if inputs.reason == "none":
            assert observation.suppress.count("1") == 0
        if inputs.reason == "inactive_destination":
            assert inputs.protocol == "cancelled", "Inactive destination must cancel before acceptance"
        if observation.stage == "settled":
            prior = self.register if inputs.destination == "register" else self.memory[inputs.address]
            assert not observation.valid or all(
                not (w == s == "1" and d != q)
                for w, s, d, q in zip(observation.write, observation.suppress, observation.data, prior, strict=True)
            ), "Integration safety assertion failed: suppressed architecturally required write"
            next_word = "".join(
                d if observation.valid and w == "1" else q
                for w, d, q in zip(observation.write, observation.data, prior, strict=True)
            )
            memory = self.memory.copy()
            register = self.register
            if inputs.destination == "register":
                register = next_word
            else:
                memory[inputs.address] = next_word
            self.pending = register, memory
            self.coverage.integration_cross.add((inputs.destination, inputs.reason, inputs.protocol, decision(observation.write, observation.suppress)))
            if inputs.destination == "memory" and observation.valid:
                self.coverage.addresses.add(inputs.address)
        elif observation.stage == "captured":
            assert self.pending is not None
            previous = self.register if inputs.destination == "register" else self.memory[inputs.address]
            counts = self.coverage.activity_counts[inputs.destination]
            counts["baseline_writes"] += observation.write.count("1") if observation.valid else 0
            counts["gated_writes"] += observation.permitted.count("1") if observation.valid else 0
            register, memory = self.pending
            expected = register if inputs.destination == "register" else memory[inputs.address]
            actual = observation.register if inputs.destination == "register" else observation.memory[
                (3 - inputs.address) * self.config.width:(4 - inputs.address) * self.config.width
            ]
            counts["baseline_state_toggles"] += sum(a != b for a, b in zip(previous, expected, strict=True))
            counts["gated_state_toggles"] += sum(a != b for a, b in zip(previous, actual, strict=True))
            self.register, self.memory = register, memory
        assert observation.register == self.register, "Register state differs from ungated reference"
        assert observation.memory == "".join(reversed(self.memory)), "Memory state differs from ungated reference"
