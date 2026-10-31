"""Only numerically checked commits and asserted directed outcomes cover goals."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector


class SftCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.hits=set()
        self.counts=Counter()
        self.cycles=0
        self.latencies={}
        self.random_cycles=0

    def hit(self,name):self.hits.add(name)

    def report(self):
        c=self.config
        goals=['validation_cancel','busy_drain','completion_event','activation','backpressure','false_suppress','validation_rejection',
               'ownership_rejection','ordered_completion','atomic_destinations',
               'suspend_resume','drain','terminate','reset_pending','counters',
               'unknown_reset','unknown_ready','metadata_rejection','empty_reduction','source_rejection','package_isolation','external_replay']
        goals += [f'operation_{n}' for n in (0,2,7,8,9)]
        goals += [f'reduction_{n}' for n in range(4)]
        goals += [f'reduction_phase_{n}' for n in range(6)]
        if c.FU_PROFILE:goals += ['operation_1','operation_3']
        if c.FU_PROFILE>=2:goals += ['operation_4','operation_5',*(f'quality_{n}' for n in range(3)),'exception_result']
        if c.CONTEXT_DEPTH>=2:goals.append('accumulator_3')
        if c.CONTEXT_DEPTH>=3:goals.append('accumulator_2')
        if c.FU_PROFILE==2:goals.append('count_limit')
        if c.FU_PROFILE==3:goals += ['operation_6','exp_base_0','exp_base_1']
        if c.SUPPORT_SATURATION:goals.append('saturation')
        if c.SUPPORT_PREDICATED_TOKEN:goals.append('false_token')
        if c.SUPPORT_INTERPOLATION:goals.append('lut_interpolation')
        if c.SUPPORT_LOCAL_CHAINING:goals.append('write_accumulator')
        if c.SUPPORT_LOCAL_CHAINING and c.BYPASS_PROFILE>=1:goals.append('write_rf')
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH>1:goals.append('temporal')
        if c.CONTROL_PROTECTION:goals.append('fault_containment')
        checks={n:n in self.hits for n in goals}
        return dict(status='PASS' if all(checks.values()) else 'FAIL',framework='PyUVM',
            parameters=c.parameters,seed=c.seed,goals=checks,cycles=self.cycles,
            counts=dict(self.counts),observed_issue_to_commit_cycles={k:sorted(v) for k,v in self.latencies.items()},random_transactions=self.random_cycles,
            hdl_assertions='NOT_RUN',lint='NOT_RUN',synthesis='Design Compiler (deferred)')
