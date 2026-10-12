"""LaneMask coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from lane_mask.constants import SOURCES
from mosaic_uvm.components import CoverageCollector


class LaneMaskCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.checks = self.random_checks = self.stable_checks = self.simultaneous_changes = 0
        self.control_violations = Counter()
        self.truth = set()
        self.individual_lanes = set()
        self.suppression = set()
        self.independence = set()
        self.populations = set()
        self.population_transitions = set()
        self.tails = set()
        self.predicates = set()
        self.valid_mask_cross = set()
        self.mask_predicate_cross = set()
        self.unknown_bins = set()
        self.invalid_unknowns = set()
        self.exhaustive = set()

    def sample(self, observation):
        config = self.config
        ports = observation.ports
        outputs = observation.outputs
        active = outputs[0]
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        for lane, values in enumerate(zip(*(reversed(word) for word in ports[1:]), strict=True)):
            self.truth.add((lane, ports[0], *values))
            for index, (name, value) in enumerate(zip(SOURCES, values, strict=True)):
                if ports[0] == "1" and value == "0" and all(other == "1" for other_index, other in enumerate(values) if other_index != index):
                    self.suppression.add((lane, name))
                if value in ("x", "z"):
                    if ports[0] == "1":
                        self.unknown_bins.add((lane, name, value))
                    elif ports[0] == "0":
                        self.invalid_unknowns.add((lane, name, value))
            if ports[0] == "0" and values == ("1", "1", "1"):
                self.suppression.add((lane, "i_operation_valid"))
        if ports[0] in ("x", "z"):
            self.unknown_bins.add((-1, "i_operation_valid", ports[0]))
        known = all(set(word) <= {"0", "1"} for word in ports)
        if known:
            population = active.count("1")
            self.populations.add(population)
            if population == 1:
                self.individual_lanes.add(active[::-1].index("1"))
            valid, mask, predicate = (int(word, 2) for word in ports[1:])
            self.valid_mask_cross.add((valid, mask))
            self.mask_predicate_cross.add((mask, predicate))
            if ports[0] == "1" and valid == predicate == config.maximum:
                if mask in ((1 << count) - 1 for count in range(config.lanes + 1)):
                    self.tails.add(mask)
            if ports[0] == "1" and valid == mask == config.maximum:
                self.predicates.add(predicate)
        if (config.lanes <= 4 and known) or config.lanes <= 2:
            self.exhaustive.add(ports)
        previous = self.previous
        if previous:
            before_ports, before_outputs = previous.ports, previous.outputs
            if ports == before_ports:
                assert outputs == before_outputs, "Unchanged inputs retained history-dependent state"
                self.stable_checks += 1
            if all(before != after for before, after in zip(before_ports, ports, strict=True)):
                self.simultaneous_changes += 1
            if set(before_outputs[0] + active) <= {"0", "1"}:
                self.population_transitions.add((before_outputs[0].count("1"), active.count("1")))
            if ports[0] == before_ports[0] == "1":
                changed = [(source, bit, old, new) for source, (old_word, new_word) in enumerate(zip(before_ports[1:], ports[1:], strict=True))
                           for bit, (old, new) in enumerate(zip(reversed(old_word), reversed(new_word), strict=True)) if old != new]
                if len(changed) == 1 and changed[0][2:] in (("0", "1"), ("1", "0")):
                    source, bit, old, new = changed[0]
                    self.independence.add((bit, SOURCES[source], old, new))
                    offset = config.lanes - bit - 1
                    for old_word, new_word in zip(before_outputs, outputs, strict=True):
                        old_others = old_word[:offset] + old_word[offset + 1:]
                        new_others = new_word[:offset] + new_word[offset + 1:]
                        assert old_others == new_others, "Another lane's control changed an output"
        self.previous = observation

    def report(self):
        config = self.config
        lanes = range(config.lanes)
        required_unknowns = set(product(lanes, SOURCES, "xz")) | {(-1, "i_operation_valid", value) for value in "xz"}
        required_cross = set(product(config.patterns, repeat=2))
        goals = {
            "every_lane_binary_truth_table": set((lane, *values) for lane in lanes for values in product("01", repeat=4)) <= self.truth,
            "every_lane_four_state_truth_table": set((lane, *values) for lane in lanes for values in product("01xz", repeat=4)) <= self.truth,
            "every_lane_active_individually": self.individual_lanes == set(lanes),
            "every_source_disables_every_lane": set(product(lanes, ("i_operation_valid", *SOURCES))) <= self.suppression,
            "bidirectional_lane_independence": set((lane, source, old, new) for lane, source in product(lanes, SOURCES) for old, new in (("0", "1"), ("1", "0"))) <= self.independence,
            "all_active_population_counts": self.populations == set(range(config.lanes + 1)),
            "all_population_transition_pairs": set(product(range(config.lanes + 1), repeat=2)) <= self.population_transitions,
            "every_contiguous_tail": self.tails == {(1 << count) - 1 for count in range(config.lanes + 1)},
            "all_predicate_patterns": set(config.patterns) <= self.predicates,
            "lane_valid_by_architectural_mask": required_cross <= self.valid_mask_cross,
            "architectural_mask_by_predicate": required_cross <= self.mask_predicate_cross,
            "known_control_assertions": required_unknowns <= self.unknown_bins and set(self.control_violations) == {"i_operation_valid", *SOURCES},
            "invalid_operation_suppresses_unknown_lane_controls": set(product(lanes, SOURCES, "xz")) <= self.invalid_unknowns,
            "simultaneous_changes_to_all_controls": self.simultaneous_changes >= 2,
            "stable_repeated_transactions": self.stable_checks >= 64,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.lanes <= 4:
            words = tuple(f"{value:0{config.lanes}b}" for value in range(config.maximum + 1))
            goals["exhaustive_binary_vectors"] = set(product("01", words, words, words)) <= self.exhaustive
        if config.lanes <= 2:
            words = tuple("".join(word) for word in product("01xz", repeat=config.lanes))
            goals["exhaustive_four_state_vectors"] = set(product("01xz", words, words, words)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL", "parameters": {"LANES": config.lanes},
            "seed": config.seed, "simulator": cocotb.SIM_NAME, "checked_transactions": self.checks,
            "random_transactions": self.random_checks, "stable_transactions": self.stable_checks,
            "expected_control_violations": dict(self.control_violations), "goals": goals,
            "bins": {"per_lane_truth_tables": sorted(self.truth), "individual_active_lanes": sorted(self.individual_lanes),
                     "source_suppression": sorted(self.suppression), "lane_independence": sorted(self.independence),
                     "populations": sorted(self.populations), "population_transitions": sorted(self.population_transitions),
                     "tail_masks": sorted(self.tails), "predicate_patterns": sorted(self.predicates),
                     "lane_valid_mask_cross": sorted(self.valid_mask_cross), "mask_predicate_cross": sorted(self.mask_predicate_cross),
                     "unknown_controls": sorted(self.unknown_bins), "invalid_operation_unknowns": sorted(self.invalid_unknowns),
                     "simultaneous_changes": self.simultaneous_changes, "vector_truth_table_entries": len(self.exhaustive)},
        }
