"""Functional goals contain only cases checked against independent expectations."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector




def required_goals(p):
    goals = set(['acknowledged_launch_visibility_and_reverse_release',
 'authorized_policy_enable_disable_query_and_destructive_cancel_bounds',
 'bounded_pending_storage_backpressures_and_drains_without_losing_descriptors',
 'cancel_retains_stalled_command_until_matching_terminal_and_rollback',
 'disjoint_concurrent_reservations_and_held_results_do_not_delay_resource_release',
 'event_sequence_gap_containment_requires_authorized_destructive_recovery',
 'foreign_duplicate_events_and_terminal_responses_cannot_complete_or_release',
 'full_array_predeclared_package_is_one_atomic_reservation',
 'held_admission_remains_immutable_through_cancel_and_precedes_terminal_result',
 'immutable_descriptor_snapshot_and_stable_action_backpressure',
 'kernel_timeout_is_an_abort_and_drain_obligation',
 'local_reset_never_clears_remote_ownership_without_global_system_recovery',
 'malformed_unknown_owner_proof_and_unsupported_descriptor_rejection',
 'no_effect_failure_at_each_launch_boundary_rolls_back_reverse_order',
 'policy_response_capacity_backpressures_requests_and_preserves_ordered_replies',
 'reset_requires_remote_clean_proof',
 'resource_wait_cancel_duplicate_identity_and_exactly_once_admission',
 'reused_performance_counters_publish_nonzero_submission_activity',
 'seeded_random_latency_backpressure_multi_owner_lifecycles',
 'start_requires_matching_input_and_output_readiness_in_prebound_epoch',
 'tag_space_exhaustion_never_wraps_and_requires_clean_recovery',
 'test_scan_clock_and_power_qualification_preserve_live_control_obligations',
 'timeout_keeps_tag_and_resources_late_success_rolls_back_or_aborts'])
    if p['ENABLE_COUNTER_FEEDBACK']:
        goals.add('coherent_snapshot_identity_generation_validity_and_critical_override')
    if p['ENABLE_COUNTER_FEEDBACK']:
        goals.add('requested_completion_snapshot_must_be_coherent_and_newer_than_compute_done')
    if p['ENABLE_DEADLINE_MONITORING']:
        goals.add('deadline_negative_slack_warns_without_becoming_completion_or_rejection')
    if p['ENABLE_SAFE_SUSPEND']:
        goals.add('safe_preserved_suspend_cookie_resume_fresh_epoch_and_old_event_quarantine')
    if p['MAX_PENDING_KERNELS'] >= 5 and p['NUM_PRIORITY_LEVELS'] > 1 and p['HIGH_PRIORITY_BURST_LIMIT'] <= 2 and p['AGE_ESCALATION_CYCLES'] >= 4096:
        goals.add('eligible_priority_burst_limit_forces_lower_rank_with_round_robin_ties')
    if p['MAX_PENDING_KERNELS'] >= 3 and p['NUM_PRIORITY_LEVELS'] > 1 and p['AGE_ESCALATION_CYCLES'] <= 16:
        goals.add('saturating_aging_promotes_old_eligible_low_priority_kernel')
    if p['NUM_CLUSTERS'] >= 2 and p['MAX_ACTIVE_KERNELS'] >= 2:
        goals.add('aggregate_bandwidth_admission_and_owner_bounds_cannot_revoke_live_reservations')
    if p['MAX_PACKAGE_VARIANTS'] >= 2 and p['MAX_ACTIVE_KERNELS'] >= 2:
        goals.add('selects_free_exact_precompiled_alternate_without_online_mapping')
    if True:
        goals.add('partial_backend_effects_are_contained_until_authorized_drain_and_release')
    if p['NUM_CLUSTERS'] >= 2 and p['MAX_PACKAGE_VARIANTS'] >= 2 and p['ENABLE_FAULT_AWARE_ALLOCATION']:
        goals.add('fault_aware_allocation_uses_healthy_precompiled_variant')
    if p['CONTROL_PROTECTION'] == 2:
        goals.add('secded_single_control_bit_corrected_and_scrubbed')
    if p['CONTROL_PROTECTION'] != 0:
        goals.add('uncorrectable_protected_control_state_fails_closed_until_reset')
    goals.add('terminal_before_command_acceptance_is_quarantined')
    goals.add('matching_terminal_on_command_acceptance_edge_completes_exactly_once')
    goals.add('same_tag_wrong_owner_or_command_cannot_retire_inflight_action')
    if p['NUM_CLUSTERS'] >= 2 and p['MAX_ACTIVE_KERNELS'] >= 2:
        goals.add('dma_memory_scratchpad_event_and_counter_conflicts_are_atomic')
    return goals


class RuntimeCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.goals = dict.fromkeys(required_goals(self.config.parameters), False)
        self.counts = Counter()
        self.cycles = 0
        self.random_transactions = 0
        self.commands = set()
        self.states = set()

    def hit(self, name):
        assert name in self.goals, ('Unplanned coverage goal', name)
        self.goals[name] = True

    def report(self):
        return dict(status='PASS' if self.goals and all(self.goals.values()) else 'FAIL',
                    parameters=self.config.parameters, seed=self.config.seed,
                    random_transactions=self.random_transactions, cycles=self.cycles,
                    goals=self.goals, counts=dict(self.counts),
                    commands=sorted(self.commands), states=sorted(self.states))
