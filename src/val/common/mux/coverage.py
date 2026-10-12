"""Mux coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from mux.model import input_words, interval_kind


class MuxCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.checks = self.held_checks = self.random_checks = self.simultaneous = 0
        self.activity = Counter()
        self.legal = set()
        self.invalid = set()
        self.unknown = set()
        self.legal_pairs = set()
        self.to_invalid = set()
        self.from_invalid = set()
        self.selected_activity = set()
        self.selected_bits = set()
        self.patterns = set()
        self.distinct = set()
        self.unselected_states = set()
        self.invalid_quiet = set()
        self.hold_classes = set()
        self.small_words = set()

    def sample(self, observation):
        config = self.config
        if observation.stage == "held":
            self.held_checks += 1
            self.hold_classes.add("long" if observation.hold_ns >= 1 else "short")
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        words = input_words(observation.packed_data, config.data_width)
        selected = int(observation.select, 2) if set(observation.select) <= {"0", "1"} else None
        legal = selected is not None and selected < config.num_inputs
        if legal:
            self.legal.add(selected)
            self.selected_bits.update((selected, bit, value) for bit, value in enumerate(reversed(observation.output)))
            self.patterns.update((selected, name) for name in pattern_classes(words[selected]))
            if observation.label == "distinct_words" and len(set(words)) == config.num_inputs:
                self.distinct.add(selected)
            if config.data_width <= 8:
                self.small_words.add((selected, words[selected]))
        elif selected is not None:
            self.invalid.add(selected)
        else:
            self.unknown.add(observation.select)
        previous = self.previous
        if previous:
            old_selected = int(previous.select, 2) if set(previous.select) <= {"0", "1"} else None
            old_legal = old_selected is not None and old_selected < config.num_inputs
            kind = interval_kind(config, previous.packed_data, previous.select, observation.packed_data, observation.select)
            assert observation.kind == kind, "Quiet-interval classification did not match actual ports"
            if old_legal and legal:
                self.legal_pairs.add((old_selected, selected))
            if old_legal and selected is not None and not legal:
                self.to_invalid.add((old_selected, selected))
            if old_selected is not None and not old_legal and legal:
                self.from_invalid.add((old_selected, selected))
            if previous.select != observation.select and previous.packed_data != observation.packed_data:
                self.simultaneous += 1
            old_words = input_words(previous.packed_data, config.data_width)
            if kind == "selected":
                self.selected_activity.add(selected)
            elif kind == "unselected":
                for index, (before, after) in enumerate(zip(old_words, words, strict=True)):
                    if before != after and len(set(after)) == 1:
                        self.unselected_states.add((selected, index, after[0]))
            elif kind == "invalid":
                self.invalid_quiet.add(observation.select)
        self.previous = observation

    def report(self):
        config = self.config
        legal = set(range(config.num_inputs))
        invalid = set(config.invalid_encodings)
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.data_width > 1:
            classes.update(("partial_unknown", "mixed_x_z"))
        unselected = {(selected, other, state) for selected, other, state in product(legal, legal, "01xz") if selected != other}
        goals = {
            "every_legal_selection": self.legal == legal,
            "every_invalid_binary_encoding": self.invalid == invalid,
            "every_four_state_unknown_selection": self.unknown == set(config.unknown_selects),
            "every_legal_transition_pair": self.legal_pairs == set(product(legal, repeat=2)),
            "every_legal_to_invalid_transition": self.to_invalid == set(product(legal, invalid)),
            "every_invalid_to_legal_transition": self.from_invalid == set(product(invalid, legal)),
            "every_selected_input_changes": self.selected_activity == legal,
            "every_selected_bit_preserves_four_states": self.selected_bits == set(product(legal, range(config.data_width), "01xz")),
            "every_input_pattern_class_selected": set(product(legal, classes)) <= self.patterns,
            "every_unselected_source_four_state_activity_suppressed": unselected <= self.unselected_states,
            "fixed_invalid_selection_suppresses_all_data_activity": ({f"{value:0{config.select_width}b}" for value in invalid} | set(config.unknown_selects)) <= self.invalid_quiet,
            "simultaneous_data_and_selection_changes": self.simultaneous > 0,
            "short_and_long_stable_intervals": self.hold_classes == {"short", "long"},
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        distinct_representable = config.num_inputs <= 1 << config.data_width
        if distinct_representable:
            goals["every_input_selected_with_distinct_source_words"] = self.distinct == legal
        if config.data_width <= 8:
            goals["exhaustive_binary_words_per_input"] = {(index, f"{value:0{config.data_width}b}") for index in legal for value in range(config.maximum + 1)} <= self.small_words
        if config.data_width <= 2:
            words = ("".join(word) for word in product("01xz", repeat=config.data_width))
            goals["exhaustive_four_state_words_per_input"] = set(product(legal, words)) <= self.small_words
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"NUM_INPUTS": config.num_inputs, "DATA_WIDTH": config.data_width,
                           "DEFAULT_VALUE": config.default_value, "SEL_WIDTH": config.select_width},
            "default_class": config.default_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "goals": goals, "legal_selection_coverage_percent": 100 * len(self.legal) / config.num_inputs,
            "invalid_encoding_coverage_percent": 100 * len(self.invalid) / len(invalid) if invalid else None,
            "distinct_words_representable": distinct_representable,
            "bins": {"legal_selections": sorted(self.legal), "invalid_encodings": sorted(self.invalid),
                     "unknown_selections": sorted(self.unknown), "legal_transition_pairs": sorted(self.legal_pairs),
                     "legal_to_invalid": sorted(self.to_invalid), "invalid_to_legal": sorted(self.from_invalid),
                     "selected_input_activity": sorted(self.selected_activity), "selected_bit_values": sorted(self.selected_bits),
                     "selected_pattern_classes": sorted(self.patterns), "distinct_words_selected": sorted(self.distinct),
                     "unselected_source_states": sorted(self.unselected_states), "invalid_quiet_selections": sorted(self.invalid_quiet),
                     "hold_classes": sorted(self.hold_classes), "simultaneous_changes": self.simultaneous,
                     "output_activity": dict(self.activity), "unique_small_width_words": len(self.small_words)},
        }
