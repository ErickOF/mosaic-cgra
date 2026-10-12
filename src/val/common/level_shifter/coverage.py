"""LevelShifter coverage components for specification-based PyUVM validation."""

from collections import Counter
import hashlib
from itertools import product
import cocotb
from level_shifter.model import pattern_classes
from mosaic_uvm.components import CoverageCollector


class LevelShifterCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.checks = self.held_checks = self.random_checks = self.output_transitions = 0
        self.bit_values = set()
        self.bit_transitions = set()
        self.classes = Counter()
        self.hold_classes = set()
        self.words = set()
        self.stimulus_hash = hashlib.sha256()

    def sample(self, observation):
        if observation.stage == "held":
            self.held_checks += 1
            self.hold_classes.add("long" if observation.hold_ns >= 1 else "short")
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        self.bit_values.update(enumerate(reversed(observation.output)))
        self.classes.update(pattern_classes(observation.source))
        if self.config.width <= 8:
            self.words.add(observation.source)
        self.stimulus_hash.update(f"{observation.label}:{observation.source}:{observation.hold_ns}\n".encode("ascii"))
        previous = self.previous
        if previous is not None:
            changed = [bit for bit, (before, after) in enumerate(zip(reversed(previous), reversed(observation.source), strict=True)) if before != after]
            if len(changed) <= 1:
                # Require an isolated bit change on each known background.
                # Repeated words cover diagonal state-to-same-state transitions.
                for bit, (before, after) in enumerate(zip(reversed(previous), reversed(observation.source), strict=True)):
                    if changed and bit != changed[0]:
                        continue
                    offset = self.config.width - bit - 1
                    others = observation.source[:offset] + observation.source[offset + 1:]
                    for background in "01":
                        if all(value == background for value in others):
                            self.bit_transitions.add((bit, background, before, after))
        self.previous = observation.source

    def report(self):
        config = self.config
        required_classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.width > 1:
            required_classes.update(("mixed_known", "mixed_unknown_known", "mixed_x_z"))
        goals = {
            "every_bit_preserves_all_four_states": self.bit_values == set(product(range(config.width), "01xz")),
            "every_bit_four_state_transition_on_both_backgrounds": self.bit_transitions == set(product(range(config.width), "01", "01xz", "01xz")),
            "all_data_pattern_classes": required_classes <= set(self.classes),
            "short_and_long_stable_intervals": self.hold_classes == {"short", "long"},
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 8:
            goals["exhaustive_binary_data"] = {f"{value:0{config.width}b}" for value in range(config.maximum + 1)} <= self.words
        if config.width <= 4:
            goals["exhaustive_four_state_data"] = {"".join(word) for word in product("01xz", repeat=config.width)} <= self.words
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "DIRECTION": config.direction},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks,
            "random_transactions": self.random_checks, "output_transitions": self.output_transitions,
            "stimulus_sha256": self.stimulus_hash.hexdigest(), "goals": goals,
            "four_state_bit_coverage_percent": 100 * len(self.bit_values) / (4 * config.width),
            "bins": {"bit_values": sorted(self.bit_values), "independent_bit_transitions": sorted(self.bit_transitions),
                     "pattern_classes": dict(self.classes), "hold_classes": sorted(self.hold_classes),
                     "unique_small_width_words": len(self.words)},
        }
