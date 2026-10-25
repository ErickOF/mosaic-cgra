"""Coverage is credited by checked issues, commits and directed outcomes."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector

class VctCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.hits = set()
        self.counts = Counter()
        self.random_cycles = 0

    def hit(self, name):
        self.hits.add(name)

    def report(self):
        c = self.config
        goals = ['activation', 'backpressure', 'false_suppress', 'write_rf', 'write_predicate',
                 'write_bypass', 'validation_rejection', 'ownership_rejection', 'ordered_completion',
                 'exact_latency', 'partial_slices', 'invalid_slice',
                 'reset_pending', 'suspend_resume', 'drain', 'counters', 'terminate', 'unknown_reset', 'runtime_context_rejection',
                 'atomic_destinations', 'local_mask', 'inactive_x', 'write_vacc', 'accumulator_feedback']
        goals += [f'opcode_{op}' for op in range(20) if op not in (18,19) or c.SUPPORT_MINMAX]
        if c.SUPPORT_MUL: goals.append('opcode_20')
        if c.SUPPORT_MAC: goals.append('opcode_21')
        goals += [f'mask_{m}' for m in range(1 << c.NUM_LANES)]
        goals += [f'format_{m}' for m in range(5)]
        goals += [f'predicate_{m}' for m in range(4)]
        if c.REQUIRE_CANONICAL_FORMAT: goals.append('format_rejection')
        else: goals.append('format_padding_allowed')
        if c.SUPPORT_PREDICATED_TOKEN: goals.append('false_token')
        if c.SUPPORT_SATURATION: goals.append('saturation')
        if c.BYPASS_PROFILE: goals.append('counter_slice_count')
        if c.FU_PROFILE:
            goals += ['write_sacc'] + [f'crossop_1_{op}' for op in range(5) if op not in (1,2) or c.SUPPORT_MINMAX]
        if c.FU_PROFILE == 2: goals.append('fu_2')
        if c.SUPPORT_BROADCAST: goals.append('fu_3')
        if c.SUPPORT_LANE_SELECT: goals.append('fu_4')
        if c.SYNC_PROFILE == 1: goals.append('rdu_delay')
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH > 1: goals.append('temporal')
        if c.CONTROL_PROTECTION or c.VRF_PROTECTION: goals.append('fault_containment')
        if c.SUPPORT_RETENTION: goals += ['retention', 'power_off']
        checks = {name: name in self.hits for name in goals}
        return dict(status='PASS' if all(checks.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, goals=checks, counts=dict(self.counts),
            random_transactions=self.random_cycles, hdl_assertions='NOT_RUN',
            synthesis='Design Compiler (deferred)')
