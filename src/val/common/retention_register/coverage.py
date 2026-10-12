"""Retention coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector


class RetentionCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.held_checks = self.random_checks = self.clocked_checks = 0
        self.command_counts, self.diagnostics, self.activity_counts = Counter(), Counter(), Counter()
        self.priority, self.saved_bits, self.restored_bits, self.saved_classes, self.interval_cross = set(), set(), set(), set(), set()
        self.reset_phases, self.release_phases, self.stopped, self.unknown_controls, self.ignored_enable = set(), set(), set(), set(), set()
        self.latest_save_restores = self.multiple_write_restores = self.legal_restores = 0

    def report(self):
        config = self.config
        diagnostic_names = {"unknown_reset", "unknown_enable", "unknown_save", "unknown_restore", "save_restore_conflict",
                            "restore_without_save", "repeat_save", "repeat_restore"}
        if config.has_enable:
            diagnostic_names.add("enable_during_retention")
        classes = {"zero", "one", "alternating", "random", "all_x", "all_z"}
        if config.width > 1:
            classes.update(("mixed_x_z", "partial_unknown"))
        goals = {
            "all_binary_control_priority_combinations": self.priority == set(product("01", repeat=4)),
            "saved_and_restored_every_bit_four_states": self.saved_bits == self.restored_bits == set(product(range(config.width), "01xz")),
            "every_saved_data_class": classes <= self.saved_classes,
            "saved_data_class_short_long_interval_cross": set(product(("zero", "one", "alternating", "random"), ("short", "long"))) <= self.interval_cross,
            "restore_after_multiple_normal_writes": self.multiple_write_restores > 0,
            "restore_of_most_recent_save": self.latest_save_restores > 0,
            "repeated_legal_save_restore_epochs": self.legal_restores >= 16,
            "all_protocol_diagnostics_active": diagnostic_names <= set(self.diagnostics),
            "every_control_x_and_z_sampled": set(product(("unknown_reset", "unknown_enable", "unknown_save", "unknown_restore"), "xz")) <= self.unknown_controls,
            "reset_assertion_and_release_both_phases": self.reset_phases == self.release_phases == {0, 1},
            "stopped_clock_holds_both_storage_images": self.stopped == {0, 1},
            "normal_capture_and_reset": self.command_counts["capture"] > 0 and self.command_counts["reset"] > 0,
            "every_transaction_checked_after_hold": self.checks == self.held_checks,
            "random_clocked_cycles": self.random_checks == config.random_cycles,
        }
        if config.has_enable:
            goals["disabled_functional_hold"] = self.command_counts["hold"] >= 16
        else:
            goals["enable_ignored_for_all_four_values"] = self.ignored_enable == set("01xz")
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "RESET_VALUE": config.reset_value, "ASYNC_RESET": int(config.async_reset), "HAS_ENABLE": int(config.has_enable)},
            "reset_class": config.reset_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "clocked_checks": self.clocked_checks,
            "random_transactions": self.random_checks, "legal_restore_epochs": self.legal_restores,
            "portable_image_assertions": "PASS" if config.check_image else "NOT_RUN", "goals": goals,
            "commands": dict(self.command_counts), "expected_protocol_violations": dict(self.diagnostics),
            "bins": {"control_priority": sorted(self.priority), "saved_bit_values": sorted(self.saved_bits), "restored_bit_values": sorted(self.restored_bits),
                     "saved_data_classes": sorted(self.saved_classes), "saved_class_interval": sorted(self.interval_cross),
                     "reset_assert_clock_phases": sorted(self.reset_phases), "reset_release_clock_phases": sorted(self.release_phases),
                     "stopped_clock_phases": sorted(self.stopped), "unknown_controls": sorted(self.unknown_controls), "ignored_enable": sorted(self.ignored_enable),
                     "output_image_transitions": dict(self.activity_counts)},
        }
