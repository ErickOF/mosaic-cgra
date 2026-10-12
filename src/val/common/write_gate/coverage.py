"""WriteGate coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector
from write_gate.model import decision, mask_class


class WriteGateCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.held_checks = self.random_checks = self.capture_checks = 0
        self.output_transitions = 0
        self.bit_states, self.bit_transitions, self.pattern_cross = set(), set(), set()
        self.populations, self.holds, self.exhaustive, self.simultaneous = set(), set(), set(), set()
        self.violations, self.integration_cross = Counter(), set()
        self.previous = None
        self.activity_counts = {
            dest: dict(baseline_writes=0, gated_writes=0, baseline_state_toggles=0, gated_state_toggles=0)
            for dest in ("register", "memory")
        }
        self.addresses = set()

    def sample(self, observation):
        config = self.config
        item = observation.item
        if observation.stage == "held":
            self.held_checks += 1
            self.holds.add((decision(observation.write, observation.suppress), "long" if item.hold_ns >= 1 else "short"))
            return
        if observation.stage == "captured":
            self.capture_checks += 1
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += item.get_name().startswith("random_")
        self.bit_states.update((bit, w, s) for bit, (w, s) in enumerate(zip(reversed(observation.write), reversed(observation.suppress), strict=True)))
        if set(observation.write + observation.suppress) <= set("01"):
            self.pattern_cross.add((mask_class(observation.write), mask_class(observation.suppress)))
            self.populations.add(sum(w == s == "1" for w, s in zip(observation.write, observation.suppress, strict=True)))
        if config.width <= 4:
            self.exhaustive.add((observation.write, observation.suppress))
        if self.previous:
            old = self.previous
            self.simultaneous.add((old.write != observation.write, old.suppress != observation.suppress))
            self.bit_transitions.update(
                (bit, ow, os_, nw, ns) for bit, (ow, os_, nw, ns) in enumerate(zip(
                    reversed(old.write), reversed(old.suppress), reversed(observation.write), reversed(observation.suppress), strict=True))
            )
        self.previous = observation

    def report(self):
        config = self.config
        classes = {"zero", "one"} | ({"alternating"} if config.width > 1 else set()) | ({"other"} if config.width > 2 else set())
        goals = {
            "every_bit_binary_truth_table": set(product(range(config.width), "01", "01")) <= self.bit_states,
            "held_check_for_every_transaction": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.integration:
            goals.update(
                destination_capture_for_every_transaction=self.capture_checks == self.checks,
                all_memory_addresses=self.addresses == set(range(4)),
                destination_reason_cross=all(any(row[:2] == (dest, reason) for row in self.integration_cross)
                                             for dest, reason in product(("register", "memory"), ("none", "redundant_value", "inactive_destination"))),
                protocol_suppression_cross=all(any(row[0] == dest and row[2:] == (protocol, mode) for row in self.integration_cross)
                                              for dest, protocol, mode in product(("register", "memory"), ("accepted", "cancelled"),
                                                                                 ("permitted", "suppressed", "mixed") if config.width > 1 else ("permitted", "suppressed"))),
                idle_destinations=all(any(row[0] == dest and row[2:] == ("idle", "no_request") for row in self.integration_cross) for dest in ("register", "memory")),
                destination_write_event_reduction=all(0 < row["gated_writes"] < row["baseline_writes"] for row in self.activity_counts.values()),
                unchanged_architectural_state_activity=all(row["baseline_state_toggles"] == row["gated_state_toggles"] for row in self.activity_counts.values()),
            )
        else:
            goals.update(
                every_bit_four_state_truth_table=set(product(range(config.width), "01xz", "01xz")) <= self.bit_states,
                every_bit_binary_control_transition=set(product(range(config.width), "01", "01", "01", "01")) <= self.bit_transitions,
                write_pattern_suppression_pattern_cross=set(product(classes, repeat=2)) <= self.pattern_cross,
                all_suppression_populations=self.populations == set(range(config.width + 1)),
                simultaneous_and_independent_changes=set(product((False, True), repeat=2)) <= self.simultaneous,
                unknown_control_assertions_active=set(self.violations) == {"unknown_write_enable", "unknown_requested_suppression"},
                short_and_long_idle_permitted_suppressed_holds=set(product(("no_request", "permitted", "suppressed"), ("short", "long"))) <= self.holds,
            )
            if config.width <= 4:
                words = [f"{value:0{config.width}b}" for value in range(1 << config.width)]
                goals["exhaustive_binary_masks"] = set(product(words, repeat=2)) <= self.exhaustive
            if config.width <= 2:
                words = ["".join(word) for word in product("01xz", repeat=config.width)]
                goals["exhaustive_four_state_masks"] = set(product(words, repeat=2)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL", "parameters": {"WIDTH": config.width},
            "integration": config.integration, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks,
            "random_transactions": self.random_checks, "destination_captures": self.capture_checks,
            "output_transitions": self.output_transitions, "expected_control_violations": dict(self.violations),
            "destination_activity": self.activity_counts if config.integration else None, "goals": goals,
            "bins": dict(bit_states=sorted(self.bit_states), bit_transitions=sorted(self.bit_transitions),
                         pattern_cross=sorted(self.pattern_cross), suppressed_populations=sorted(self.populations),
                         holds=sorted(self.holds), simultaneous_changes=sorted(self.simultaneous),
                         integration_cross=sorted(self.integration_cross), memory_addresses=sorted(self.addresses)),
        }
