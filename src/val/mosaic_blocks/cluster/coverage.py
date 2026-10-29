"""Coverage is earned by checked public transactions and independent predictions."""
from collections import Counter
import os
from mosaic_uvm.components import CoverageCollector

class ClusterCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cycles = 0
        self.bins = Counter()
        required=('coordinated_reset','runtime_exact_once','runtime_held',
            'generated_four_by_four_control') if os.getenv('CLUSTER_MODE')=='smoke' else (
            'coordinated_reset','runtime_exact_once','runtime_held','config_held','event_held',
            'completion_held','package_held','kernel_completion_exact_once',
            'architecture_topology_manifest','bad_image_crc_rejected','package_binding_rejected',
            'configuration_multicast_exact_once','real_endpoint_images_validated',
            'coordinated_native_commit','load_compute_store_real_sram','exact_committed_bytes',
            'release_waits_for_obligations','owner_isolation','coherent_counter_snapshot',
            'idle_clock_gate','boundary_held','suspend_resume_identity_preserved',
            'boundary_metadata_all_bits_preserved','optional_power_rejected','orderly_drain',
            'native_fault_containment','protected_controller_fail_stop','random_clock_wakeup',
            'unknown_runtime_fail_closed','new_owner_has_no_stale_snapshot_or_region',
            'abort_preserves_accepted_stores','protected_event_collector_fail_stop')
        if not self.config.parameters['clock_gating']:
            required=tuple('compute_abort_at_empty_boundary' if n=='orderly_drain' else n
                           for n in required)
        if os.getenv('CLUSTER_MODE')=='partial':
            required=('coordinated_reset','runtime_exact_once','runtime_held','config_held',
                'package_held','architecture_topology_manifest','bad_image_crc_rejected',
                'package_binding_rejected','configuration_multicast_exact_once',
                'real_endpoint_images_validated','partial_commit_requires_reset')
        self.goals=dict.fromkeys(required,False)

    def hit(self, name):
        self.bins[name] += 1
        self.goals[name] = True

    def report(self):
        return dict(status='PASS' if all(self.goals.values()) else 'FAIL',
            goals=self.goals, bins=dict(self.bins), cycles=self.cycles,
            parameters=self.config.parameters, seed=self.config.seed,
            random_cycles=self.config.random_cycles,
            manifest_sha256=self.config.manifest['manifest_sha256'],
            hdl_assertions='NOT_RUN', lint='NOT_RUN',
            synthesis='Design Compiler (deferred)')
