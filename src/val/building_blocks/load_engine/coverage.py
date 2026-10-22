"""Mandatory functional goals, ownership accounting and qualification limits."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from load_engine.model import number, signed


class LoadEngineCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.modes_sizes = set()
        self.strides = set()
        self.occupancies = set()
        self.tags = set()
        self.errors = set()
        self.fatal_occupancies = set()
        self.unknowns = set()
        self.memory_error_positions = set()
        self.accounting = {}
        self.random_transactions = self.storage_checks = 0

    def record(self, events, obs, model, plan):
        c = self.config
        p = plan['p']
        self.events.update(events)
        self.random_transactions += int(obs.item.random)
        self.occupancies.add(len(model.pending))
        self.accounting = dict(accepted=model.accepted, delivered=model.delivered,
                               discarded=model.discarded, outstanding=len(model.pending))
        for name, raw in obs.item.pre.ports.items():
            if name.startswith('i_') and number(raw) is None:
                self.unknowns.add(name)
        if not obs.item.edge or not plan['run']:
            return
        if plan['start']:
            self.modes_sizes.add((p['i_mode'], p['i_element_size_log2']))
            if p['i_mode']:
                stride = signed(p['i_inner_stride'], c.ADDR_WIDTH)
                self.strides.add((stride > 0) - (stride < 0))
        if plan['fatal']:
            self.errors.add(plan['fatal'])
            self.fatal_occupancies.add(int(obs.item.pre.ports['o_outstanding'], 2))
        if plan['request']:
            tag = number(obs.item.pre.ports['o_mem_req_tag'])
            self.tags.add(tag)
            if tag == c.MAX_OUTSTANDING - 1:
                self.events['wrap'] += 1
                if obs.item.random:
                    self.events['random_wrap'] += 1
        if plan['response'] and not plan['rsp_error']:
            if p['i_mem_rsp_error']:
                target = plan['target']
                self.memory_error_positions.add('first' if target['first'] else
                    'last' if target['last'] else 'middle')
            rank = next(i for i, e in enumerate(model.pending)
                        if e['tag'] == p['i_mem_rsp_tag'])
            self.events['head_response' if rank == 0 else 'younger_response'] += 1
            if rank and obs.item.random:
                self.events['random_reordering'] += 1
        if plan['request'] and plan['response'] and plan['stream']:
            self.events['three_transfers'] += 1
        if number(obs.item.pre.ports['o_mem_req_valid']) and p['i_mem_req_ready'] == 0:
            self.events['request_stall'] += 1
            if obs.item.random:
                self.events['random_request_stall'] += 1
        if number(obs.item.pre.ports['o_stream_valid']) and p['i_stream_ready'] == 0:
            self.events['stream_stall'] += 1
            if obs.item.random:
                self.events['random_stream_stall'] += 1
        if model.pending and model.pending[0]['response'] is None:
            self.events['oldest_wait'] += 1
        if number(obs.ports['o_completed_with_error']):
            self.events['completed_with_error'] += 1

    def report(self):
        c = self.config
        required = ('start', 'request', 'response', 'stream', 'finish', 'fail', 'memory_error',
                    'fatal', 'clear', 'reset', 'wrap', 'request_stall', 'stream_stall', 'oldest_wait',
                    'completed_with_error', 'random_wrap', 'random_request_stall', 'random_stream_stall')
        goals = {n: self.events[n] > 0 for n in required}
        goals.update(every_mode_size=self.modes_sizes == {
            (m, s) for m in range(3) for s in range(c.max_log2 + 1)},
            stride_signs=self.strides == ({-1, 0, 1} if c.ADDR_WIDTH > 1 else {-1, 0}),
            every_occupancy=self.occupancies == set(range(c.MAX_OUTSTANDING + 1)),
            every_tag=self.tags == set(range(c.MAX_OUTSTANDING)),
            memory_error_positions=self.memory_error_positions == {'first', 'middle', 'last'},
            random_campaign=self.random_transactions == c.random_cycles,
            knownness_tests=len(self.unknowns) >= 10,
            ownership_accounting=bool(self.accounting) and self.accounting['outstanding'] == 0 and
                self.accounting['accepted'] == self.accounting['delivered'] + self.accounting['discarded'])
        expected_errors = {1, 2, 3, 4, 9, 10, 13, 14, 15}
        if c.max_log2:
            expected_errors |= {6, 7, 8}
        if c.max_log2 < (1 << c.aliases['ELEMENT_SIZE_WIDTH']) - 1:
            expected_errors.add(5)
        if c.MAX_OUTSTANDING < 1 << c.aliases['TAG_WIDTH']:
            expected_errors.add(12)
        if c.check_internals:
            expected_errors.add(11)
            goals['payload_storage'] = self.storage_checks > 0
        goals['fatal_classes'] = expected_errors <= self.errors
        if c.MAX_OUTSTANDING > 1:
            goals['response_reordering'] = self.events['younger_response'] > 0
            goals['random_reordering'] = self.events['random_reordering'] > 0
        if c.MAX_OUTSTANDING >= 3:
            goals['simultaneous_three_interfaces'] = self.events['three_transfers'] > 0
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
                    parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
                    observations=dict(self.observations), accounting=self.accounting,
                    random_transactions=self.random_transactions, storage_checks=self.storage_checks,
                    modes_sizes=sorted(self.modes_sizes), strides=sorted(self.strides),
                    occupancies=sorted(self.occupancies), tags=sorted(self.tags),
                    error_classes=sorted(self.errors), fatal_occupancies=sorted(self.fatal_occupancies),
                    memory_error_positions=sorted(self.memory_error_positions),
                    unknown_fields=sorted(self.unknowns),
                    hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft',
                        'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
