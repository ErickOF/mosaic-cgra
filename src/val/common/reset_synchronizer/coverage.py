"""ResetSynchronizer coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
import cocotb
from mosaic_uvm.components import CoverageCollector
from reset_synchronizer.constants import PHASES


class ResetSynchronizerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.held_checks = self.random_checks = self.unknown_violations = 0
        self.transitions = Counter()
        self.phases, self.contexts, self.reassertions, self.stops, self.pulses = set(), set(), set(), set(), set()
        self.unknowns, self.unknown_sources, self.progress, self.release_counts = set(), set(), set(), set()
        self.releases = self.asynchronous_assertions = 0

    def report(self):
        config = self.config
        goals = {
            "assert_deassert_all_clock_phases": set(product(("assert", "deassert"), PHASES)) <= self.phases,
            "running_stopped_reset_transition_cross": set(product(("assert", "deassert"), ("running", "stopped"))) <= self.contexts,
            "reassert_every_release_stage_in_both_phases": set(product(range(config.stages), "01")) <= self.reassertions,
            "stopped_clock_every_pending_stage_in_both_phases": set(product(range(config.stages), "01")) <= self.stops,
            "every_release_progress_count": self.progress == set(range(config.stages + 1)),
            "release_exactly_stages_rising_edges": self.releases > 0 and self.release_counts == {config.stages},
            "asynchronous_assertion_without_clock": self.asynchronous_assertions >= 2,
            "modeled_short_pulse_in_both_clock_phases": self.pulses == {"0", "1"},
            "known_and_asserted_sources_to_x_and_z": set(product("01", "xz")) <= self.unknown_sources,
            "active_unknown_reset_assertions": self.unknowns == {"x", "z"},
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_clock_reset_actions": self.random_checks == config.random_cycles,
        }
        return {
            "status": "PASS" if all(goals.values()) else "FAIL", "parameters": {"STAGES": config.stages},
            "seed": config.seed, "simulator": cocotb.SIM_NAME, "clock_period_ps": config.period_ps,
            "near_edge_offset_ps": config.near_ps, "modeled_pulse_width_ps": config.pulse_ps,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "expected_unknown_violations": self.unknown_violations, "release_events": self.releases,
            "portable_stage_assertions": "PASS" if config.check_stages else "NOT_RUN", "goals": goals,
            "bins": {"reset_transition_phases": sorted(self.phases), "reset_transition_clock_context": sorted(self.contexts),
                     "reassertion_stage_phase": sorted(self.reassertions), "stopped_stage_phase": sorted(self.stops),
                     "release_progress_counts": sorted(self.progress), "release_edge_counts": sorted(self.release_counts),
                     "short_pulse_phases": sorted(self.pulses), "unknown_reset_sources": sorted(self.unknown_sources),
                     "output_stage_transitions": dict(self.transitions)},
        }
