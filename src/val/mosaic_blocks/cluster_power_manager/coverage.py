"""Checked functional goals, event/command counts and physical clock activity."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector


class PowerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.goals = dict.fromkeys((
            'boot_qualifies_physical_state_resets_tiles_and_revalidates_endpoints',
            'complete_drain_and_real_tile_idle_precede_glitch_free_root_shutdown',
            'always_on_event_wakes_stopped_functional_clock_and_revalidates_identity',
            'authorized_full_identity_and_atomic_policy_rejection_without_physical_effects',
            'uncharacterized_retention_off_dvfs_and_reserved_flags_are_rejected',
            'every_tile_endpoint_and_cluster_subsystem_blocks_shutdown_until_drained',
            'every_stall_reason_preserves_required_group_clocks_without_idle_qualification',
            'every_enabled_wake_source_survives_clock_stop_and_preserves_attribution',
            'disabled_and_stale_wake_identity_cannot_restart_or_deisolate',
            'ordinary_residency_is_enforced_and_mandatory_runtime_wake_bypasses_it',
            'held_terminal_is_immutable_during_mandatory_wake',
            'diagnostic_overflow_and_stalled_events_do_not_block_wake_or_first_fatal',
            'cancel_before_effects_rolls_back_and_cancel_after_stop_queues_wake',
            'drain_timeout_obeys_rollback_policy_and_late_physical_ack_cannot_release_fault',
            'power_clock_voltage_and_thermal_faults_contain_before_authorized_recovery',
            'first_error_is_sticky_and_recovery_requires_reset_reload_and_fresh_validation',
            'allocation_rebind_and_stale_boot_serial_identity_tag_replies_require_fresh_proof',
            'incomplete_validation_contains_and_stalled_validation_record_is_stable',
            'test_scan_mbist_are_isolated_authorized_rows_and_exit_reloads_before_release',
            'unknown_command_policy_wake_and_live_control_never_authorize_physical_effects',
            'seeded_random_commands_activity_wakes_and_backpressure_leave_no_obligations',
            'counter_snapshot_and_disabled_counter_contracts',
        ), False)
        p = self.config.parameters
        self.goals[('automatic_gate_uses_exact_consecutive_threshold_and_clears_on_interruption' if p['AUTO_CLOCK_GATE_ENABLE'] else
            'statically_disabled_automatic_gating_cannot_be_enabled_by_policy')] = False
        self.goals[('protected_control_storage_fault_is_contained_with_known_physical_outputs' if p['CONTROL_PROTECTION'] else
            'unprotected_profile_has_known_registered_physical_controls')] = False
        if p['CONTROL_PROTECTION'] == 2:
            self.goals['secded_corrects_single_bit_control_storage_fault'] = False
        self.goals.update(dict.fromkeys((
            'coordinated_reset_reconciles_each_startup_and_gate_phase',
            'power_glitch_requires_full_requalification_and_startup_ack_timeouts_contain',
            'clock_stop_and_validation_timeout_cannot_be_released_by_late_reply'), False))
        self.counts = Counter()
        self.cycles = 0
        self.clock_edges = {}
        self.states = set()
        self.phases = set()
        self.random_transactions = 0

    def hit(self, name):
        assert name in self.goals, ('Undeclared coverage goal', name)
        self.goals[name] = True

    def report(self):
        return dict(status='PASS' if all(self.goals.values()) else 'FAIL', parameters=self.config.parameters, seed=self.config.seed,
                    cycles=self.cycles, counts=dict(self.counts), goals=self.goals,
                    clock_edges=self.clock_edges, states=sorted(self.states), phases=sorted(self.phases),
                    random_transactions=self.random_transactions)
