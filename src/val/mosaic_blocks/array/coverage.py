"""Only checked functional behavior earns an explicitly declared coverage goal."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector

class ArrayCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cycles = 0
        self.bins = Counter()
        names = ['reset', 'runtime_exact_once', 'runtime_held', 'owner_isolation',
            'generation_isolation', 'overlap_rejected', 'unsupported_unchanged',
            'manifest_discovery', 'hierarchical_config', 'prepare_before_commit',
            'atomic_commit', 'load_compute_store', 'exact_bytes', 'event_held',
            'completion_exact_once', 'release', 'random_stalls', 'test_mode',
            'unknown_fail_closed', 'concurrent_allocations', 'fault_containment', 'suspend_resume']
        if len(self.config.parameters['clusters']) > 1:
            names += ['noc_configuration', 'noc_packet_conservation', 'package_rebinding',
                      'noc_backpressure']
        import os
        if os.getenv('ARRAY_MODE') == 'partial_commit':
            names = ['reset', 'manifest_discovery', 'runtime_exact_once', 'runtime_held',
                     'hierarchical_config', 'prepare_before_commit', 'noc_configuration', 'partial_commit']
        if os.getenv('ARRAY_MODE') == 'concurrent':
            names = ['reset', 'manifest_discovery', 'runtime_exact_once', 'runtime_held',
                     'hierarchical_config', 'prepare_before_commit', 'atomic_commit',
                     'noc_configuration', 'concurrent_kernels', 'completion_exact_once']
        self.goals = dict.fromkeys(names, False)

    def hit(self, name):
        if name in self.goals: self.goals[name] = True
        self.bins[name] += 1

    def report(self):
        return dict(status='PASS' if all(self.goals.values()) else 'FAIL', goals=self.goals,
            bins=dict(self.bins), cycles=self.cycles, parameters=self.config.parameters,
            seed=self.config.seed, random_cycles=self.config.random_cycles,
            manifest_sha256=self.config.manifest['manifest_sha256'], hdl_assertions='NOT_RUN',
            lint='NOT_RUN', synthesis='Design Compiler (deferred)')
