"""IsolationCell coverage components for specification-based PyUVM validation."""

from collections import Counter, defaultdict
from itertools import product
import cocotb
from isolation_cell.model import isolation_state, pattern_classes
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.logic import bits


class IsolationCellCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.checks = self.random_checks = self.control_violations = self.output_transitions = 0
        self.states = Counter()
        self.passed_bits = set()
        self.clamped_bits = set()
        self.assert_patterns = set()
        self.release_patterns = set()
        self.quiet_patterns = set()
        self.activity_states = set()
        self.control_unknowns = set()
        self.merge_bins = set()
        self.patterns_by_state = defaultdict(set)
        self.exhaustive = set()

    def sample(self, observation):
        config = self.config
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        state = isolation_state(observation.isolate, config.active_high)
        self.states[state] += 1
        self.patterns_by_state[state].update(pattern_classes(observation.data))
        if config.width <= 4:
            self.exhaustive.add((observation.isolate, observation.data))
        if state == "inactive":
            self.passed_bits.update(enumerate(reversed(observation.output)))
        elif state == "active":
            assert set(observation.output) <= {"0", "1"}, "An isolated output became unknown"
            self.clamped_bits.update(range(config.width))
            if observation.continuously_isolated:
                self.quiet_patterns.add(observation.data)
        else:
            for bit, (value, clamp) in enumerate(zip(reversed(observation.data), reversed(config.clamp_bits), strict=True)):
                relation = "equal" if value == clamp else value if value in ("x", "z") else "different"
                self.merge_bins.add((bit, observation.isolate, relation))
        previous = self.previous
        if previous:
            before = isolation_state(previous.isolate, config.active_high)
            if before == "inactive" and state == "active" and previous.data == observation.data:
                self.assert_patterns.add(observation.data)
            if before == "active" and state == "inactive" and previous.data == observation.data:
                self.release_patterns.add(observation.data)
            if before == state and previous.data != observation.data:
                self.activity_states.add(state)
        self.previous = observation

    def report(self):
        config = self.config
        patterns = set(config.directed_patterns)
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.width > 1:
            classes.add("mixed_x_z")
        goals = {
            "all_isolation_states": set(self.states) == {"active", "inactive", "unknown"},
            "every_bit_passes_all_four_states": set(product(range(config.width), "01xz")) <= self.passed_bits,
            "every_bit_clamps": self.clamped_bits == set(range(config.width)),
            "assertion_every_directed_pattern": patterns <= self.assert_patterns,
            "release_every_directed_pattern": patterns <= self.release_patterns,
            "isolated_data_activity_no_output_changes": patterns <= self.quiet_patterns,
            "data_activity_before_during_after_isolation": {"active", "inactive"} <= self.activity_states,
            "all_pattern_classes_pass_and_clamp": all(classes <= self.patterns_by_state[state] for state in ("active", "inactive")),
            "unknown_control_assertions": self.control_unknowns == {"x", "z"},
            "unknown_control_merge_every_bit": set(product(range(config.width), ("x", "z"), ("equal", "different", "x", "z"))) <= self.merge_bins,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 4:
            words = ("".join(bits) for bits in product("01xz", repeat=config.width))
            goals["exhaustive_four_state_truth_table"] = set(product("01xz", words)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "CLAMP_VALUE": config.clamp_value,
                           "ISOLATE_ACTIVE_HIGH": int(config.active_high)},
            "clamp_class": config.clamp_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "random_transactions": self.random_checks,
            "output_transitions": self.output_transitions, "expected_control_violations": self.control_violations,
            "goals": goals, "passed_bit_coverage_percent": 100 * len(self.passed_bits) / (4 * config.width),
            "bins": {"isolation_states": dict(self.states), "passed_bit_values": sorted(self.passed_bits),
                     "clamped_bits": sorted(self.clamped_bits), "assert_patterns": sorted(self.assert_patterns),
                     "release_patterns": sorted(self.release_patterns), "quiet_patterns": sorted(self.quiet_patterns),
                     "data_activity_states": sorted(self.activity_states), "unknown_controls": sorted(self.control_unknowns),
                     "merge_bins": sorted(self.merge_bins), "pattern_classes": {key: sorted(value) for key, value in self.patterns_by_state.items()},
                     "four_state_truth_table_entries": len(self.exhaustive) if config.width <= 4 else None},
        }
