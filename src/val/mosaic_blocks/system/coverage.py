"""Coverage goals are awarded only after assertions in the sequence/checker pass."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector

class SystemCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cycles=0
        self.bins=Counter()
        names=['reset_discovery','control_exact_once','control_held','illegal_registers',
            'owner_isolation','descriptor_snapshot','buffer_fence','program_completion',
            'memory_bounds','memory_backpressure','event_head_atomic','event_ack','irq_mask',
            'unknown_control','counter_snapshot','random_controls']
        if self.config.mode=='full':
            names += ['configuration_dma','coordinated_commit','input_dma','actual_compute',
                'output_dma','write_commit_order','fenced_host_completion','release','actual_mst_bytes']
            if self.config.parameters['clusters']>1: names += ['real_noc']
        if self.config.mode=='core':
            names += ['descriptor_rejections','stale_generation','dma_bounds_rejection',
                'cancel_drains_burst','completion_waits_write_and_fence','memory_timeout_late_drain',
                'wrong_memory_identity','wrong_array_identity','sticky_region_integrity','reset_recovery','command_queue_full_wrap',
                'event_full_backpressure','unmasked_event_behind_head']
        self.goals=dict.fromkeys(names,False)

    def hit(self,name):
        if name in self.goals: self.goals[name]=True
        self.bins[name]+=1

    def report(self):
        return dict(status='PASS' if all(self.goals.values()) else 'FAIL',goals=self.goals,
            bins=dict(self.bins),cycles=self.cycles,parameters=self.config.parameters,
            seed=self.config.seed,random_cycles=self.config.random_cycles,
            manifest_sha256=self.config.manifest['manifest_sha256'],hdl_assertions='NOT_RUN',
            lint='NOT_RUN',synthesis='Design Compiler (deferred)')
