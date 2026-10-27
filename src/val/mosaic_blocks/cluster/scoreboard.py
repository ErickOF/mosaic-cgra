"""Independent transaction ownership, stability and reliable event checks."""
from collections import deque
from pyuvm import ConfigDB, uvm_subscriber

class ClusterScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.active = ConfigDB().get(self, '', 'active')
        self.runtime = deque()
        self.config_tags = set()
        self.held = {}
        self.sequence_id = 0
        self.native_completions = set()
        self.kernel_completions = set()

    def write(self, obs):
        p = obs.ports
        if obs.phase != 'pre':
            return
        self.coverage.cycles += 1
        if not p['i_rstb']:
            self.runtime.clear()
            self.config_tags.clear()
            self.held.clear()
            self.sequence_id = 0
            self.native_completions.clear()
            self.kernel_completions.clear()
            return
        for name in ('o_runtime_ready', 'o_runtime_response_valid', 'o_cfg_request_ready',
                     'o_cfg_response_valid', 'o_event_valid', 'o_status_cluster_state',
                     'o_status_error', 'o_status_quiescent', 'o_cluster_clock_enable'):
            assert p[name] is not None, ('Unknown public control', name, obs.item.get_name())
        channels = [
            ('package', 'o_package_response_valid', 'i_package_response_ready', 'o_package_response_'),
            ('runtime', 'o_runtime_response_valid', 'i_runtime_response_ready', 'o_runtime_response_'),
            ('config', 'o_cfg_response_valid', 'i_cfg_response_ready', 'o_cfg_response_'),
            ('event', 'o_event_valid', 'i_event_ready', 'o_event_'),
            ('completion', 'o_mst_completion_valid', 'i_mst_completion_ready', 'o_mst_completion_')]
        for key, valid, ready, prefix in channels:
            fields = tuple((n, p[n]) for n in p if n.startswith(prefix))
            if key in self.held:
                assert p[valid] == 1 and fields == self.held[key], (
                    'Changed a backpressured output', key, obs.item.get_name())
                self.coverage.hit(key + '_held')
            if p[valid] and p[ready] != 1:
                self.held[key] = fields
            else:
                self.held.pop(key, None)
        for port in range(self.c.manifest['geometry']['mesh']['B']):
            key = ('boundary', port)
            valid = (p['o_boundary_valid'] >> port) & 1
            ready = (p['i_boundary_ready'] >> port) & 1
            fields = (p['o_boundary_data'] >> (32*port) & 0xffffffff,
                      p['o_boundary_metadata'] >> (512*port) & ((1<<512)-1))
            if key in self.held:
                assert valid and fields == self.held[key], ('Boundary changed while stalled',port)
                self.coverage.hit('boundary_held')
            if valid and not ready: self.held[key] = fields
            else: self.held.pop(key,None)
        if p['i_runtime_valid'] and p['o_runtime_ready']:
            self.runtime.append((p['i_runtime_command'], p['i_runtime_tag']))
        if p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
            assert self.runtime and self.runtime.popleft() == (
                p['o_runtime_response_command'], p['o_runtime_response_tag'])
            self.coverage.hit('runtime_exact_once')
        if p['i_cfg_request_valid'] and p['o_cfg_request_ready']:
            tag = p['i_cfg_request_tag']
            assert tag not in self.config_tags
            self.config_tags.add(tag)
        if p['o_cfg_response_valid'] and p['i_cfg_response_ready']:
            tag = p['o_cfg_response_tag']
            assert tag in self.config_tags, ('Unowned config response', tag)
            if p['o_cfg_response_last']:
                self.config_tags.remove(tag)
        if p['o_event_valid'] and p['i_event_ready']:
            assert p['o_event_sequence'] == self.sequence_id, ('Event loss or duplicate', p)
            self.sequence_id += 1
            key = (p['o_event_owner_id'], p['o_event_kernel_id'], p['o_event_package_id'],
                   p['o_event_epoch'])
            if p['o_event_type'] == 0 and p['o_event_payload'] & 7 == 0:
                token = key, p['o_event_source_id']
                assert token not in self.native_completions, 'Duplicate native completion'
                self.native_completions.add(token)
            if p['o_event_type'] == 2:
                assert key not in self.kernel_completions, 'Duplicate kernel completion'
                self.kernel_completions.add(key)
                ids = set(self.c.manifest['tile_id_table'])
                assert {source for identity, source in self.native_completions if identity == key} == ids
                assert p['o_status_completion_mask'] == self.c.manifest['tile_present_mask']
                assert not p['o_status_scratchpad_busy'] and not p['o_status_network_busy']
                self.coverage.hit('kernel_completion_exact_once')

    def check_phase(self):
        assert not self.runtime and not self.config_tags, 'Unretired accepted commands'
