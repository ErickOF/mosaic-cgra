"""Passive public-boundary ledger: handshakes, ownership, event sequencing and hold."""
from collections import deque
from pyuvm import ConfigDB, uvm_subscriber

class ArrayScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.pending = deque()
        self.held = {}
        self.events = set()
        self.event_sequence = 0

    def write(self, observation):
        if observation.phase != 'pre': return
        p = observation.ports
        self.coverage.cycles += 1
        if not p['i_rstb']:
            self.pending.clear(); self.held.clear(); self.events.clear(); self.event_sequence = 0
            return
        for name in ('o_runtime_ready', 'o_runtime_response_valid', 'o_event_valid',
                     'o_allocated', 'o_running', 'o_fatal', 'o_array_state', 'o_interrupt'):
            if name in p: assert p[name] is not None, ('Unknown control', name)
        for channel, valid, ready, prefix in (
            ('runtime', 'o_runtime_response_valid', 'i_runtime_response_ready', 'o_runtime_response_'),
            ('event', 'o_event_valid', 'i_event_ready', 'o_event_'),
            ('configuration', 'o_cfg_response_valid', 'i_cfg_response_ready', 'o_cfg_response_')):
            if valid not in p: continue
            payload = tuple((name, p[name]) for name in p if name.startswith(prefix))
            if channel in self.held:
                assert p[valid] and payload == self.held[channel], ('Unstable output', channel)
                self.coverage.hit(channel+'_held')
            if p[valid] and not p[ready]: self.held[channel] = payload
            else: self.held.pop(channel, None)
        if p['i_runtime_valid'] and p['o_runtime_ready']:
            self.pending.append((p['i_runtime_command'], p['i_runtime_tag'], p['i_runtime_cluster_mask']))
        if p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
            assert self.pending and self.pending.popleft() == (p['o_runtime_response_command'],
                p['o_runtime_response_tag'], p['o_runtime_response_cluster_mask'])
            self.coverage.hit('runtime_exact_once')
        n = len(self.c.parameters['clusters'])
        groups = [p['o_group_masks'] >> (c*n) & ((1<<n)-1) for c in range(n)]
        for c in range(n):
            if p['o_allocated'] >> c & 1:
                assert groups[c] >> c & 1
                for k in range(n):
                    if groups[c] >> k & 1:
                        assert groups[k] == groups[c]
                        for name, width in [('o_owner_ids',16), ('o_kernel_ids',16),
                                            ('o_array_package_ids',32), ('o_allocation_generations',16)]:
                            assert (p[name] >> (c*width) & ((1<<width)-1)) == (
                                p[name] >> (k*width) & ((1<<width)-1)), ('Cross-owner group', name)
        if p.get('o_event_valid', 0) and p['i_event_ready']:
            assert p['o_event_sequence'] == self.event_sequence
            self.event_sequence += 1
            if p['o_event_type'] == 2:
                key = tuple(p[k] for k in ('o_event_owner_id', 'o_event_kernel_id',
                    'o_event_package_id', 'o_event_epoch', 'o_event_cluster_mask'))
                assert key not in self.events, 'Duplicate array completion'
                self.events.add(key)
                assert p['o_completion_mask'] & p['o_event_cluster_mask'] == p['o_event_cluster_mask']
                assert p.get('o_noc_idle', 1), 'Premature completion with NoC packets'
                self.coverage.hit('completion_exact_once')

    def check_phase(self):
        assert not self.pending, 'Accepted runtime command has no terminal response'
