"""PriorityEncoder coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector
from priority_encoder.model import pattern_classes


class PriorityEncoderCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.checks = self.held_checks = self.random_checks = self.ambiguity_violations = 0
        self.activity = Counter()
        self.populations, self.selected, self.pairs, self.population_cross = set(), set(), set(), set()
        self.extremes, self.pattern_cross, self.bits_seen, self.bit_transitions = set(), set(), set(), set()
        self.unknown_cases, self.masked_activity, self.winner_pairs, self.holds = set(), set(), set(), set()
        self.binary_vectors, self.four_state_vectors = set(), set()
        self.unknown_modes = Counter()

    def sample(self, record):
        config = self.config
        observation, reference = record
        if observation.stage == "held":
            self.held_checks += 1
            if not reference.unknown:
                count = len(reference.known)
                self.holds.add(("none" if count == 0 else "single" if count == 1 else "multiple", "long" if observation.hold_ns >= 1 else "short"))
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        self.bits_seen.update(enumerate(reversed(observation.request)))
        if config.width <= 5:
            self.four_state_vectors.add(observation.request)
        if not reference.unknown:
            population = len(reference.known)
            self.populations.add(population)
            if config.width <= 8:
                self.binary_vectors.add(observation.request)
            if population:
                self.selected.add(reference.selected)
                self.population_cross.add((reference.selected, population))
                self.extremes.add((min(reference.known), max(reference.known)))
            if population == 2:
                self.pairs.add(tuple(sorted(reference.known)))
            classes = pattern_classes(int(observation.request, 2), config.width)
            if observation.label.startswith("random_"):
                classes.add("random")
            self.pattern_cross.update((name, observation.outputs[3]) for name in classes)
        else:
            self.unknown_modes["ambiguous" if reference.ambiguous else "masked"] += 1
            best_known = (min(reference.known) if config.lsb_high_priority else max(reference.known)) if reference.known else None
            for index in reference.unknown:
                relation = "no_known" if best_known is None else "higher" if config.higher(index, best_known) else "lower"
                self.unknown_cases.add((index, observation.request[config.width - index - 1], relation))
        if self.previous:
            previous, old_reference = self.previous
            self.bit_transitions.update((index, before, after) for index, (before, after) in enumerate(zip(reversed(previous.request), reversed(observation.request), strict=True)))
            if old_reference.selected is not None and reference.selected is not None:
                self.winner_pairs.add((old_reference.selected, reference.selected))
                if old_reference.selected == reference.selected:
                    for index, (before, after) in enumerate(zip(reversed(previous.request), reversed(observation.request), strict=True)):
                        if before != after and config.higher(reference.selected, index):
                            self.masked_activity.add((reference.selected, index, after))
        self.previous = observation, reference

    def report(self):
        config = self.config
        classes = {("none", "0"), ("single", "0"), ("all", "1" if config.width > 1 else "0"),
                   ("contiguous", "0"), ("random", "0")}
        if config.width > 1:
            classes.update((("pair", "1"), ("contiguous", "1"), ("random", "1")))
        if config.width > 2:
            classes.add(("noncontiguous", "1"))
        for pattern in ("01", "10"):
            classes.add(("alternating", "1" if int((pattern * config.width)[:config.width], 2).bit_count() > 1 else "0"))
        unknown_bins = {(index, state, "no_known") for index, state in product(range(config.width), "xz")}
        for index, other, state in product(range(config.width), range(config.width), "xz"):
            if index != other:
                unknown_bins.add((index, state, "higher" if config.higher(index, other) else "lower"))
        masked = {(winner, other, state) for winner, other, state in product(range(config.width), range(config.width), "01xz") if config.higher(winner, other)}
        contention = {index for index, count in config.population_cross if count > 1}
        hold_states = {"none", "single", "multiple"} if config.width > 1 else {"none", "single"}
        goals = {
            "every_request_selected": self.selected == set(range(config.width)),
            "every_population_count": self.populations == set(range(config.width + 1)),
            "every_simultaneous_request_pair": self.pairs == {(low, high) for low in range(config.width) for high in range(low + 1, config.width)},
            "reachable_selected_index_population_cross": self.population_cross == config.population_cross,
            "every_eligible_index_selected_under_contention": {index for index, count in self.population_cross if count > 1} == contention,
            "lowest_highest_asserted_index_cross": self.extremes == {(low, high) for low in range(config.width) for high in range(low, config.width)},
            "pattern_class_multiple_cross": classes <= self.pattern_cross,
            "every_request_bit_four_states": self.bits_seen == set(product(range(config.width), "01xz")),
            "every_request_bit_ordered_four_state_transition": self.bit_transitions == set(product(range(config.width), "01xz", "01xz")),
            "unknown_higher_lower_and_no_known_cases": unknown_bins <= self.unknown_cases,
            "lower_priority_activity_preserves_winner": masked <= self.masked_activity,
            "every_ordered_winner_transition": self.winner_pairs == set(product(range(config.width), repeat=2)),
            "active_ambiguous_request_assertions": self.ambiguity_violations > 0,
            "short_and_long_holds_by_population_class": set(product(hold_states, ("short", "long"))) <= self.holds,
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 8:
            goals["exhaustive_binary_request_vectors"] = self.binary_vectors == {f"{value:0{config.width}b}" for value in range(config.maximum + 1)}
        if config.width <= 5:
            goals["exhaustive_four_state_request_vectors"] = self.four_state_vectors == {"".join(word) for word in product("01xz", repeat=config.width)}
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "LSB_HIGH_PRIORITY": int(config.lsb_high_priority), "INDEX_WIDTH": config.index_width},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "expected_ambiguity_violations": self.ambiguity_violations, "output_transitions": dict(self.activity),
            "goals": goals, "selected_index_coverage_percent": 100 * len(self.selected) / config.width,
            "contention_ineligible_indices": sorted(set(range(config.width)) - contention),
            "bins": {"selected_indices": sorted(self.selected), "populations": sorted(self.populations),
                     "request_pairs": sorted(self.pairs), "selected_index_population": sorted(self.population_cross),
                     "lowest_highest_indices": sorted(self.extremes), "pattern_multiple": sorted(self.pattern_cross),
                     "request_bit_values": sorted(self.bits_seen), "request_bit_transitions": sorted(self.bit_transitions),
                     "unknown_cases": sorted(self.unknown_cases), "unknown_modes": dict(self.unknown_modes),
                     "masked_request_activity": sorted(self.masked_activity), "winner_transitions": sorted(self.winner_pairs),
                     "holds": sorted(self.holds), "binary_vectors": len(self.binary_vectors) if config.width <= 8 else None,
                     "four_state_vectors": len(self.four_state_vectors) if config.width <= 5 else None},
        }
