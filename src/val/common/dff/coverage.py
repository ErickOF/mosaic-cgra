"""Dff coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector


class DffCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.state = None  # The spec does not define an unreset power-up value.
        self.ignore_start = 0
        self.ignored_intervals = []
        self.expected_changes = []
        self.output_changes = []
        self.commands = Counter()
        self.checks = self.random_checks = 0
        self.reset_enable = set()
        self.reset_release = set()
        self.data_activity = set()
        self.enable_transitions = set()
        self.bit_values = set()
        self.unknown_controls = set()
        self.ignored_enable = set()
        self.masked_unknown_enable = set()
        self.short_reset_phases = set()
        self.command_pairs = set()
        self.longest_runs = Counter()

    def report(self):
        config = self.config
        expected_unknowns = set(product(("rstb",), ("x", "z"), ("0", "1")))
        if config.has_enable:
            expected_unknowns |= set(product(("enable",), ("x", "z"), ("1",)))
        intervals = self.ignored_intervals + ([(self.ignore_start, float("inf"))] if self.ignore_start is not None else [])
        actual = [
            (change.time_ps, change.before, change.after) for change in self.output_changes
            if not any(start <= change.time_ps <= end for start, end in intervals)
        ]
        goals = {
            "reset_while_enabled_and_disabled": {"0", "1"} <= self.reset_enable,
            "reset_release_before_rising_edge": "0" in self.reset_release,
            "short_reset_pulses_in_both_phases": self.short_reset_phases == {"low", "high"},
            "capture": self.commands["capture"] > 0,
            "consecutive_captures": self.longest_runs["capture"] >= 16,
            "every_bit_zero_and_one": set(product(range(config.width), ("0", "1"))) <= self.bit_values,
            "data_changes_in_both_phases": set(product(("low", "high"), ("0", "1"))) <= self.data_activity,
            "enable_transitions_in_both_phases": set(product(("low", "high"), ("0", "1"))) <= self.enable_transitions,
            "known_control_assertions": expected_unknowns <= self.unknown_controls,
            "reset_masks_unknown_enable": self.masked_unknown_enable == {"x", "z"},
            "random_cycles": self.random_checks == config.random_cycles,
            "complete_output_waveform": actual == self.expected_changes,
            "final_state_known": self.state is not None and set(self.state) <= {"0", "1"},
        }
        if config.has_enable:
            goals["consecutive_holds"] = self.longest_runs["hold"] >= 16
            goals["alternating_capture_and_hold"] = {("capture", "hold"), ("hold", "capture")} <= self.command_pairs
        else:
            goals["ignored_enable_all_four_states"] = self.ignored_enable == {"0", "1", "x", "z"}
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "RESET_VALUE": config.reset_value,
                           "ASYNC_RESET": int(config.async_reset), "HAS_ENABLE": int(config.has_enable)},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_snapshots": self.checks, "clocked_checks": sum(self.commands.values()) - self.commands["async_assert"],
            "random_cycles": self.random_checks, "output_transitions": len(actual),
            "expected_control_violations": len(self.unknown_controls),
            "commands": dict(self.commands), "longest_runs": dict(self.longest_runs),
            "goals": goals, "bit_value_coverage_percent": 100 * len(self.bit_values) / (2 * config.width),
            "bins": {"reset_enable": sorted(self.reset_enable), "reset_release_clock": sorted(self.reset_release),
                     "short_reset_phases": sorted(self.short_reset_phases), "data_activity": sorted(self.data_activity),
                     "command_pairs": sorted(self.command_pairs),
                     "enable_transitions": sorted(self.enable_transitions), "bit_values": sorted(self.bit_values),
                     "unknown_controls": sorted(self.unknown_controls), "ignored_enable": sorted(self.ignored_enable)},
            "waveform_mismatch": None if actual == self.expected_changes else {
                "expected": self.expected_changes, "actual": actual,
            },
        }
