"""Check public protocols, immutable records, isolation and exactly-once obligations."""
from pyuvm import ConfigDB, uvm_subscriber
from runtime_controller.config import WIDTHS, CODES, unpack
from runtime_controller.model import Ledger, lane


class RuntimeScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.ledger = Ledger(self.c.parameters)
        self.holds = {}
        self.admissions = []
        self.results = []
        self.policy_replies = []
        self.actions = []
        self.policy_tags = set()
        self.policy_pending = set()

    def held(self, key, valid, ready, payload):
        if key in self.holds:
            assert valid and payload == self.holds[key], ('Changed stalled record', key)
        if valid and not ready:
            self.holds[key] = payload
            self.coverage.counts['stalled_cycles'] += 1
        else:
            self.holds.pop(key, None)

    def write(self, observation):
        p = observation.ports
        c = self.coverage
        c.cycles += 1
        if p['i_rstb'] == 0:
            c.counts['reset_discards'] += self.ledger.outstanding
            self.ledger = Ledger(self.c.parameters)
            self.holds.clear()
            self.policy_pending.clear()
            self.policy_tags.clear()
            return
        if p['i_rstb'] is None:
            return
        if not (p['i_clock_ready'] and p['i_power_good']) or p['i_test_mode'] or p['i_scan_enable']:
            self.holds.clear()
            return
        if p['o_integrity_error']:
            assert self.active.get('expect_fault'), 'Unexpected protected-state fault'
            self.holds.clear()
            return
        if p['o_submit_ready'] and p['i_submit_valid']:
            self.ledger.submit(p)
            c.counts['submitted'] += 1
        for name in ('admission', 'result', 'policy_response', 'runtime_event'):
            valid, ready, bits = (p[f'o_{name}_valid'], p[f'i_{name}_ready'], p[f'o_{name}_record'])
            self.held(name, valid, ready, bits)
            if valid and ready:
                kind = dict(admission='notice', result='notice', policy_response='policy_reply',
                            runtime_event='diagnostic')[name]
                record = unpack(kind, bits)
                if name == 'admission':
                    self.ledger.admission(record)
                    self.admissions.append(record)
                elif name == 'result':
                    self.ledger.result(record)
                    self.results.append(record)
                elif name == 'policy_response':
                    assert record['tag'] in self.policy_pending, ('Unmatched policy reply', record)
                    self.policy_pending.remove(record['tag'])
                    self.policy_replies.append(record)
                c.counts[name] += 1
        if p['i_policy_valid'] and p['o_policy_ready']:
            policy = unpack('policy', p['i_policy_record'])
            assert policy['tag'] not in self.policy_tags
            self.policy_tags.add(policy['tag'])
            self.policy_pending.add(policy['tag'])
        for ep in range(7):
            prefix = 'array_runtime' if ep == 6 else 'service'
            index = 0 if ep == 6 else ep
            valid = p[f'o_{prefix}_valid'] >> index & 1
            ready = p[f'i_{prefix}_ready'] >> index & 1
            bits = lane(p[f'o_{prefix}_record'], index, WIDTHS['action'])
            self.held(('command', ep), valid, ready, bits)
            if valid and ready:
                action = unpack('action', bits)
                self.ledger.command(ep, action)
                self.actions.append((ep, action))
                c.commands.add(f'{ep}:{action["command"]}')
                c.counts['actions'] += 1
        for ep in range(7):
            prefix = 'array_runtime' if ep == 6 else 'service'
            index = 0 if ep == 6 else ep
            if p[f'i_{prefix}_response_valid'] >> index & p[f'o_{prefix}_response_ready'] >> index & 1:
                ack = unpack('ack', lane(p[f'i_{prefix}_response_record'], index, WIDTHS['ack']))
                if self.ledger.response(ep, ack):
                    c.counts['matching_responses'] += 1
                else:
                    c.counts['quarantined_responses'] += 1
        reserved = 0
        live_masks = []
        active = 0
        totals = dict(dma_mask=0, memory_mask=0, scratchpad_mask=0, event_mask=0, counter_mask=0,
                      memory_bandwidth=0, noc_bandwidth=0, power=0)
        for s in range(self.c.parameters['MAX_PENDING_KERNELS']):
            if p['o_record_valid'] >> s & 1:
                state = lane(p['o_record_state'], s, 5)
                c.states.add(state)
                mask = lane(p['o_record_cluster_mask'], s, 16)
                if p['o_record_reserved'] >> s & 1:
                    assert mask and not (mask & reserved), ('Shadow allocation overlap', s)
                    reserved |= mask
                    active += 1
                    identity = lane(p['o_record_identity'], s, WIDTHS['identity'])
                    from runtime_controller.model import key
                    descriptor = self.ledger.records[key(identity)].descriptor
                    resources = unpack('resource', descriptor['resource_record'])
                    for resource in totals:
                        if resource.endswith('_mask'):
                            assert not (totals[resource] & resources[resource]), ('Resource overlap', resource)
                            totals[resource] |= resources[resource]
                        else:
                            totals[resource] += resources[resource]
        assert p['o_active_count'] == active
        assert p['o_cluster_reserved_mask'] == reserved
        for resource, output in dict(dma_mask='o_dma_reserved_mask', memory_mask='o_memory_reserved_mask',
                scratchpad_mask='o_scratchpad_reserved_mask', event_mask='o_event_reserved_mask',
                counter_mask='o_counter_reserved_mask', memory_bandwidth='o_memory_bandwidth_reserved',
                noc_bandwidth='o_noc_bandwidth_reserved', power='o_power_reserved').items():
            assert p[output] == totals[resource], ('Shadow accounting drift', resource)
        for resource, capacity in [('memory_bandwidth', 'MEMORY_BANDWIDTH_CAPACITY'),
                                    ('noc_bandwidth', 'NOC_BANDWIDTH_CAPACITY'), ('power', 'POWER_CAPACITY')]:
            assert totals[resource] <= self.c.parameters[capacity]
        assert p['o_active_count'] <= self.c.parameters['MAX_ACTIVE_KERNELS']
        assert p['o_pending_count'] <= self.c.parameters['MAX_PENDING_KERNELS']
        if p['o_quiescent'] and not (p['i_submit_valid'] and p['o_submit_ready']):
            assert not p['o_cluster_reserved_mask'] and not p['o_active_count']
            assert not self.ledger.pending and not self.ledger.outstanding

    def check_phase(self):
        assert self.ledger.outstanding == 0, ('Unretired kernel obligations', self.ledger.outstanding)
        assert not self.ledger.pending and not self.policy_pending
        assert not self.holds, ('Stalled output left at end', self.holds)
