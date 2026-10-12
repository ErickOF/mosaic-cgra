"""Decoder coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector


class DecoderCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.previous = None
        self.checks = 0
        self.random_checks = 0
        self.legal = set()
        self.invalid = set()
        self.disabled = set()
        self.disabled_quiet = set()
        self.activated = set()
        self.legal_pairs = set()
        self.legal_to_invalid = set()
        self.invalid_to_legal = set()
        self.enable_transitions = set()
        self.simultaneous = set()
        self.unknown_enable = set()
        self.unknown_select = set()
        self.full_unknown_select = set()
        self.mixed_unknown_select = set()
        self.activity = Counter()

    def sample(self, observation):
        config = self.config
        decoded = int(observation.decoded, 2)
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        selected = int(observation.select, 2) if set(observation.select) <= {"0", "1"} else None
        if selected is not None:
            if observation.enable == "0":
                self.disabled.add(selected)
                if observation.continuously_disabled:
                    self.disabled_quiet.add(selected)
            elif observation.enable == "1":
                (self.legal if selected < config.num_outputs else self.invalid).add(selected)
            else:
                self.unknown_enable.add((observation.enable, selected))
        else:
            for index, value in enumerate(reversed(observation.select)):
                if value in ("x", "z"):
                    self.unknown_select.add((index, value, observation.enable))
            if len(set(observation.select)) == 1:
                self.full_unknown_select.add((observation.select[0], observation.enable))
            if {"x", "z"} <= set(observation.select):
                self.mixed_unknown_select.add(observation.enable)
        if decoded:
            self.activated.add(decoded.bit_length() - 1)
        previous = self.previous
        if previous is not None:
            before = int(previous.select, 2) if set(previous.select) <= {"0", "1"} else None
            if before is not None and selected is not None:
                if previous.enable == observation.enable == "1":
                    if before < config.num_outputs and selected < config.num_outputs:
                        self.legal_pairs.add((before, selected))
                    elif before < config.num_outputs:
                        self.legal_to_invalid.add((before, selected))
                    elif selected < config.num_outputs:
                        self.invalid_to_legal.add((before, selected))
                if previous.enable in ("0", "1") and observation.enable in ("0", "1") and previous.enable != observation.enable:
                    if before == selected:
                        self.enable_transitions.add((selected, observation.enable))
                    else:
                        self.simultaneous.add(observation.enable)
        self.previous = observation

    def report(self):
        config = self.config
        goals = {
            "every_legal_selection": set(range(config.num_outputs)) <= self.legal,
            "every_invalid_encoding": set(config.invalid_encodings) <= self.invalid,
            "disabled_every_encoding": set(config.encodings) <= self.disabled,
            "disabled_selection_no_activity": set(config.encodings) <= self.disabled_quiet,
            "all_legal_pairs": set(product(range(config.num_outputs), repeat=2)) <= self.legal_pairs,
            "all_legal_to_invalid_pairs": set(product(range(config.num_outputs), config.invalid_encodings)) <= self.legal_to_invalid,
            "all_invalid_to_legal_pairs": set(product(config.invalid_encodings, range(config.num_outputs))) <= self.invalid_to_legal,
            "enable_assert_deassert_every_encoding": set(product(config.encodings, ("0", "1"))) <= self.enable_transitions,
            "simultaneous_enable_and_selection": self.simultaneous == {"0", "1"},
            "every_output_bit": set(range(config.num_outputs)) <= self.activated,
            "unknown_enable_every_encoding": set(product(("x", "z"), config.encodings)) <= self.unknown_enable,
            "unknown_select_every_bit": set(product(range(config.select_width), ("x", "z"), ("0", "1"))) <= self.unknown_select,
            "all_x_all_z_selections": set(product(("x", "z"), ("0", "1"))) <= self.full_unknown_select,
            "random_activity": self.random_checks >= config.random_cycles,
        }
        if config.select_width > 1:
            goals["mixed_x_z_selections"] = self.mixed_unknown_select == {"0", "1"}
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"NUM_OUTPUTS": config.num_outputs, "SELECT_WIDTH": config.select_width},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "random_transactions": self.random_checks,
            "output_activity": dict(self.activity), "goals": goals,
            "legal_selection_coverage_percent": 100 * len(self.legal) / config.num_outputs,
            "invalid_encoding_coverage_percent": 100 * len(self.invalid) / len(config.invalid_encodings) if config.invalid_encodings else None,
            "invalid_encoding_coverage_applicable": bool(config.invalid_encodings),
            "legal_pair_coverage_percent": 100 * len(self.legal_pairs) / config.num_outputs ** 2,
            "bins": {
                "legal_selections": sorted(self.legal), "invalid_encodings": sorted(self.invalid),
                "disabled_selections": sorted(self.disabled), "disabled_quiet_selections": sorted(self.disabled_quiet),
                "activated_output_bits": sorted(self.activated), "legal_pairs": sorted(self.legal_pairs),
                "legal_to_invalid_pairs": sorted(self.legal_to_invalid), "invalid_to_legal_pairs": sorted(self.invalid_to_legal),
                "enable_transitions": sorted(self.enable_transitions),
                "unknown_enable": sorted(self.unknown_enable), "unknown_select": sorted(self.unknown_select),
                "all_unknown_select": sorted(self.full_unknown_select),
                "mixed_unknown_select_enable": sorted(self.mixed_unknown_select),
            },
        }
