"""Coverage goals are recorded only after checked transfers and responses."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector

class NocCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.hits=set();self.counts=Counter();self.cycles=0
        self.classes=set();self.pairs=set();self.random_cycles=0

    def hit(self,name):self.hits.add(name)

    def report(self):
        goals=['configuration','crc_rejection','ownership','inactive_start','backpressure',
            'drain','flush','stale_epoch','fault_rejection','sequence','random','reset_pending',
            'all_pairs','all_classes','selected_drain','held_response','binding']
        if self.config.parameters['ENABLE_LINK_PARITY']:goals+=['parity_containment']
        if self.config.parameters['DRAIN_TIMEOUT_CYCLES']<=256:goals+=['timeout']
        if self.config.parameters['NOC_PROFILE']!=0:goals+=['request_reservation','critical_progress']
        return dict(status='PASS' if all(n in self.hits for n in goals) else 'FAIL',
            framework='PyUVM',parameters=self.config.parameters,seed=self.config.seed,
            goals={n:n in self.hits for n in goals},cycles=self.cycles,counts=dict(self.counts),
            classes=sorted(self.classes),pairs=sorted(self.pairs),random_transactions=self.random_cycles,
            validation_mode='Python-only',hdl_assertions='NOT_RUN',lint='NOT_RUN',
            formal='NOT_RUN',synthesis='Design Compiler (deferred)')
