"""Mandatory goals are populated by checked sequences and scoreboard results."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector


class ScratchpadCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.counts = Counter()
        c = self.config
        goals = ['reset', 'drain', 'local_error', 'random_multi_client', 'storage_faults',
            'flush_preserves_storage', 'pipeline_flush', 'reset_preserves_storage',
            'unknown_control_containment', 'stale_internal_completion']
        if c.REGION_GENERATION_WIDTH <= 3:
            goals += ['generation_wrap_refusal_reprovision']
        else:
            goals += ['all_sizes_positions', 'bank_region_boundaries',
                'management_compare_and_stall', 'full_occupancy_backpressure', 'fence']
            if c.ENFORCE_REGIONS:
                goals += ['invalid_contents', 'ownership_permissions']
            if c.NUM_REGIONS > 1:
                goals += ['atomic_swap' if c.SUPPORT_DOUBLE_BUFFER else 'swap_disabled']
        if c.NUM_BANKS > 1 and c.NUM_CLIENTS > 1:
            goals += ['parallel_banks']
        if c.NUM_CLIENTS > 1:
            goals += ['conflict']
        if c.PROTECTION_MODE:
            goals += ['uncorrectable']
        if c.PROTECTION_MODE == 2:
            goals += ['corrected']
        if c.CONTROL_PROTECTION:
            goals += ['control_fault']
        goals += ['clock_gate_wake', 'off_ownership_refusal', 'destructive_off',
            'reload_after_off'] if c.SUPPORT_BANK_POWER_GATING else ['power_disabled']
        if c.SUPPORT_BANK_RETENTION:
            goals += ['retention', 'reset_power_transition']
        self.goals = dict.fromkeys(goals, False)
        self.errors = Counter()
        self.sizes = Counter()
        self.banks = Counter()

    def hit(self, name):
        self.goals[name] = True

    def report(self):
        return dict(status='PASS' if self.goals and all(self.goals.values()) else 'FAIL',
            parameters=self.config.parameters, seed=self.config.seed,
            random_transactions=self.counts['random_cycles'],
            goals=self.goals, counts=dict(self.counts), error_codes=dict(self.errors),
            sizes=dict(self.sizes), banks=dict(self.banks), framework='PyUVM',
            hdl_assertions='NOT_RUN', synthesis='Design Compiler (deferred)')
