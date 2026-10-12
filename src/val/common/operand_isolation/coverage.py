"""OperandIsolation coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes


class OperandIsolationCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.controls = []
        self.checks = self.held_checks = self.random_checks = self.output_transitions = 0
        self.states = Counter()
        self.control_violations = Counter()
        self.bit_values = set()
        self.patterns = set()
        self.state_activity = set()
        self.transitions = set()
        self.bit_transitions = set()
        self.unknown_relations = set()
        self.back_to_back = set()
        self.holds = set()
        self.exhaustive = set()

    def sample(self, observation):
        config = self.config
        if observation.stage == "held":
            self.held_checks += 1
            self.holds.add((observation.isolate, "long" if observation.hold_ns >= 1 else "short"))
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        control = observation.isolate
        self.states[control] += 1
        self.patterns.update((control, name) for name in pattern_classes(observation.data))
        self.bit_values.update((control, bit, value) for bit, value in enumerate(reversed(observation.data)))
        if control in "xz":
            for bit, (value, clamp) in enumerate(zip(reversed(observation.data), reversed(config.clamp_bits), strict=True)):
                relation = "equal" if value == clamp else value if value in "xz" else "different"
                self.unknown_relations.add((control, bit, relation))
        if config.width <= 8:
            self.exhaustive.add((control, observation.data))
        previous = self.previous
        if previous:
            changed = previous.data != observation.data
            self.transitions.add((previous.isolate, control, changed))
            if previous.isolate == control:
                self.state_activity.add((control, changed))
                self.bit_transitions.update(
                    (control, bit, before, after)
                    for bit, (before, after) in enumerate(zip(reversed(previous.data), reversed(observation.data), strict=True))
                    if before != after
                )
        self.controls.append(control)
        if len(self.controls) >= 3:
            self.back_to_back.add("".join(self.controls[-3:]))
        self.previous = observation

    def report(self):
        config = self.config
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.width > 1:
            classes.update(("partial_unknown", "mixed_x_z"))
        goals = {
            "all_four_control_states": set(self.states) == set("01xz"),
            "every_pattern_in_both_known_modes": set(product("01", classes)) <= self.patterns,
            "every_input_bit_four_states_in_both_modes": set(product("01", range(config.width), "01xz")) <= self.bit_values,
            "state_cross_stable_and_changing_data": set(product("01xz", (False, True))) <= self.state_activity,
            "control_transition_cross_data_activity": set(product("01xz", "01xz", (False, True))) <= self.transitions,
            "every_transparent_bit_four_state_transition": {
                ("0", bit, before, after) for bit, before, after in product(range(config.width), "01xz", "01xz") if before != after
            } <= self.bit_transitions,
            "every_bit_toggles_both_ways_while_isolated": set(product("1", range(config.width), "01", "01")) - {
                ("1", bit, state, state) for bit, state in product(range(config.width), "01")
            } <= self.bit_transitions,
            "unknown_control_poison_with_equal_different_x_z_data": set(product("xz", range(config.width), ("equal", "different", "x", "z"))) <= self.unknown_relations,
            "known_control_assertions_detect_x_and_z": set(self.control_violations) == set("xz"),
            "back_to_back_assertion_and_release": {"010", "101"} <= self.back_to_back,
            "short_and_long_holds_in_both_known_modes": set(product("01", ("short", "long"))) <= self.holds,
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 8:
            goals["exhaustive_binary_data_in_both_modes"] = set(product("01", (f"{value:0{config.width}b}" for value in range(config.maximum + 1)))) <= self.exhaustive
        if config.width <= 2:
            words = ("".join(word) for word in product("01xz", repeat=config.width))
            goals["exhaustive_four_state_truth_table"] = set(product("01xz", words)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "CLAMP_VALUE": config.clamp_value},
            "clamp_class": config.clamp_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "output_transitions": self.output_transitions, "expected_control_violations": dict(self.control_violations),
            "goals": goals,
            "bins": {"control_states": dict(self.states), "bit_values": sorted(self.bit_values),
                     "pattern_classes": sorted(self.patterns), "state_data_activity": sorted(self.state_activity),
                     "control_transition_data_activity": sorted(self.transitions), "bit_transitions": sorted(self.bit_transitions),
                     "unknown_control_data_relations": sorted(self.unknown_relations), "back_to_back": sorted(self.back_to_back),
                     "hold_classes": sorted(self.holds), "small_truth_table_entries": len(self.exhaustive) if config.width <= 8 else None},
        }
