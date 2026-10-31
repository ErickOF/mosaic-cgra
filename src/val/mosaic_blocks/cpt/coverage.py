"""Checked goals and reproducible Python-only validation evidence."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector

class CptCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.hits=set()
        self.counts=Counter()
        self.cycles=0
        self.random_cycles=0

    def hit(self,name):self.hits.add(name)

    def report(self):
        goals=['activation','validation_rejection','predicate','comparison','registers',
            'events','wait_any','wait_all','barrier','loop','backpressure','random',
            'false_suppress','ownership','duplicate','saturation','suspend_resume',
            'drain','reset_pending','unknown_ready','unknown_reset','loop_suspend','completion','bounded_loop','zero_trip']
        if self.config.LOOP_EXPORT_LEVELS>1:goals+=['multiple_exports']
        if self.config.EVENT_PROTECTION:goals+=['event_fault']
        if self.config.CONTEXT_DEPTH>1:goals+=['context_chain']
        if self.config.FU_PROFILE:goals += ['action']
        if self.config.FU_PROFILE and self.config.SUPPORT_CLUSTER_LIFECYCLE:goals+=['action_drain']
        if self.config.FU_PROFILE and self.config.SUPPORT_TIMEOUT and self.config.SUPPORT_CLUSTER_LIFECYCLE:
            goals += ['rejection','timeout_query']
        return dict(status='PASS' if all(n in self.hits for n in goals) else 'FAIL',
            framework='PyUVM',parameters=self.config.parameters,seed=self.config.seed,
            goals={n:n in self.hits for n in goals},cycles=self.cycles,
            counts=dict(self.counts),random_transactions=self.random_cycles,
            hdl_assertions='NOT_RUN',lint='NOT_RUN',synthesis='Design Compiler (deferred)')
