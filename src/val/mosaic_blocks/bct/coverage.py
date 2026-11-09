"""Mandatory functional goals are based on checked traffic and directed outcomes."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector


class BctCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.hits = set()
        self.counts = Counter()
        self.random_cycles = 0

    def hit(self, name):
        self.hits.add(name)

    def report(self):
        from mosaic_uvm.tile_selection import selection_report
        if (selected := selection_report(self)) is not None:
            return selected
        c = self.config
        goals = ['activation', 'backpressure', 'false_suppress', 'write_rf',
                 'write_predicate', 'predicate_0', 'predicate_1', 'predicate_2', 'predicate_3',
                 'validation_rejection', 'ownership_rejection', 'suspend_resume', 'terminate',
                 'reset_pending', 'ordered_completion', 'counters', 'source_classes', 'atomic_destinations', 'exact_latency', 'invalid_local_source',
                 'runtime_context_rejection', 'unknown_reset']
        goals += [f'opcode_{n}' for n in range(20 if c.SUPPORT_MINMAX else 18)]
        goals += [f'fu_{n}' for n in range(c.FU_PROFILE + 1)]
        goals += [f'input_{n}' for n in range(c.DATA_INPUT_PORTS)]
        goals += [f'output_{n}' for n in range(c.DATA_OUTPUT_PORTS)]
        if c.SUPPORT_PREDICATED_TOKEN: goals.append('false_token')
        if c.BYPASS_PROFILE or c.FU_PROFILE == 2: goals.append('write_bypass')
        if c.FU_PROFILE == 2: goals += ['write_accumulator', 'accumulator_feedback']
        if c.FU_PROFILE == 2 and c.CONTEXT_DEPTH > 1: goals.append('accumulator_type_rejection')
        if c.SUPPORT_SATURATION: goals.append('saturation')
        if c.FU_PROFILE: goals += ['canonical_rejection', 'signed_multiply']
        if c.SYNC_PROFILE == 1: goals.append('rdu_delay')
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH > 1: goals += ['temporal', 'conditional_temporal']
        if c.DATA_WIDTH > 256: goals.append('striped_rf')
        if c.SUPPORT_RETENTION: goals += ['retention', 'power_off']
        if c.CONTROL_PROTECTION or c.RF_PROTECTION: goals.append('fault_containment')
        checks = {name: name in self.hits for name in goals}
        return dict(status='PASS' if all(checks.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, goals=checks, counts=dict(self.counts),
            random_transactions=self.random_cycles, hdl_assertions='NOT_RUN',
            synthesis='Design Compiler (deferred)')
