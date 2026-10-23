"""Mandatory checked pairing, fault, ordering, mask and recovery coverage."""

from collections import Counter
from mosaic_uvm.components import CoverageCollector
from store_engine.model import number


class StoreEngineCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.modes_sizes = set()
        self.crosses = {}
        self.occupancies = {0}
        self.tags = set()
        self.errors = set()
        self.stream_fields = set()
        self.memory_positions = set()
        self.fault_positions = set()
        self.fault_classes_positions = set()
        self.mode_signs = set()
        self.transitions = set()
        self.reset_states = set()
        self.poison_positions = set()
        self.unknowns = set()
        self.accounting = {}
        self.random_transactions = self.storage_checks = self.gating_checks = self.counter_checks = 0
        self.saturated = False

    def reset_observed(self, active, error, occupancy):
        state = ('draining' if error else 'active') if active else 'idle'
        bins = self.crosses.setdefault('reset_engine_state', Counter())
        bins[str((self.config.ASYNC_RESET, state, occupancy))] += 1
        self.reset_states.add(state)

    def record(self, events, obs, model, plan):
        c, p = self.config, plan['p']
        self.events.update(events)
        self.random_transactions += obs.item.random
        self.occupancies.add(len(model.pending))
        self.accounting = dict(accepted=model.accepted, retired=model.retired,
                               discarded=model.discarded, outstanding=len(model.pending),
                               legal_beats=model.legal_beats)
        for name, raw in obs.item.pre.ports.items():
            if name.startswith('i_') and number(raw) is None:
                self.unknowns.add(name)
        def cross(name, *values):
            self.crosses.setdefault(name, Counter())[str(tuple(values))] += 1

        if not obs.item.edge:
            return
        occupancy = plan['prior_occupancy']
        if p['i_rstb'] == 0:
            self.reset_observed(plan['prior_active'], plan['prior_error'], occupancy)
        if not plan['run']:
            return
        cross('capacity_occupancy', c.MAX_OUTSTANDING, occupancy)
        current = len(model.pending)
        if occupancy == 0 and current > 0:
            self.transitions.add('empty_to_nonempty')
        if occupancy < c.MAX_OUTSTANDING and current == c.MAX_OUTSTANDING:
            self.transitions.add('nonfull_to_full')
        if occupancy == c.MAX_OUTSTANDING and current < c.MAX_OUTSTANDING:
            self.transitions.add('full_to_nonfull')
        cross('transfer_combination', plan['request'], plan['response'], plan['retire'])
        if plan['start']:
            self.modes_sizes.add((p['i_mode'], p['i_element_size_log2']))
            cross('mode_size_data_width', p['i_mode'], p['i_element_size_log2'], c.DATA_WIDTH)
            for field in ('i_inner_stride', 'i_outer_stride'):
                if p['i_mode'] == 0 or (field == 'i_outer_stride' and p['i_mode'] != 2):
                    continue
                stride = p[field]
                sign = -1 if stride & (1 << (c.ADDR_WIDTH - 1)) else int(stride != 0)
                cross('mode_stride_sign', p['i_mode'], field, sign)
                self.mode_signs.add((p['i_mode'], field, sign))
        if plan['fatal']:
            cross('fatal_response_order', plan['fatal'], bool(plan['prior_reordered']))
        if plan['bad_stream']:
            cross('stream_fault_prior_writes', plan['stream_error'], plan['prior_cursor'])
            self.fault_classes_positions.add((plan['stream_error'], plan['prior_cursor'] > 0))
        if plan['issuing'] and p['i_stream_valid'] == 0:
            cross('starvation_occupancy', occupancy)
        if plan['finish'] or plan['fail']:
            d = p if plan['desc_error'] or plan['start'] else plan['prior_descriptor']
            if d:
                outcome = 'failed' if plan['fail'] else (
                    'memory_error' if model.events['o_completed_with_error'] else 'success')
                cross('metadata_outcome', d['i_channel_id'], d['i_context_id'], outcome)
                if plan['finish']:
                    cross('memory_error_completion', bool(model.memory_error), outcome)
        if plan['fatal']:
            self.errors.add(plan['fatal'])
        if plan['request']:
            tag = number(obs.item.pre.ports['o_mem_req_tag'])
            self.tags.add(tag)
            cross('tag_wrap', tag, tag == c.MAX_OUTSTANDING - 1)
            if tag == c.MAX_OUTSTANDING - 1:
                self.events['wrap'] += 1
                if obs.item.random:
                    self.events['random_wrap'] += 1
        if plan['response'] and not plan['rsp_error']:
            target = plan['target']
            if p['i_mem_rsp_error']:
                self.memory_positions.add('first' if target['first'] else
                                          'last' if target['last'] else 'middle')
            # Use the pre-edge head even if another entry retires on this edge.
            reordered = target['tag'] != plan['prior_head']
            cross('response_order_request_ready', reordered, p['i_mem_req_ready'])
            if reordered:
                self.events['reordering'] += 1
                if obs.item.random:
                    self.events['random_reordering'] += 1
        if plan['request'] and plan['response'] and plan['retire']:
            self.events['three_transfers'] += 1
        if plan['finish'] and plan['retiring_error'] and obs.item.pre.ports['o_memory_error_seen'] == '0':
            self.events['final_error_included'] += 1
        if plan['bad_stream'] and plan['stream_error'] == 17:
            e = plan['expected']
            self.poison_positions.add('first' if e['first'] else 'last' if e['last'] else 'middle')
        if plan['bad_stream']:
            self.fault_positions.add('empty' if number(obs.item.pre.ports['o_outstanding']) == 0 else 'owned')
            label = obs.item.get_name()
            if label.startswith('fault:'):
                self.stream_fields.add(label.split(':')[1])
            if (number(obs.item.pre.ports['o_outstanding']) == c.MAX_OUTSTANDING and
                    p['i_mem_req_ready'] == 0):
                self.events['malformed_when_full_and_blocked'] += 1
        if plan['issuing'] and p['i_stream_valid'] == 0:
            self.events['starvation'] += 1
            if obs.item.random:
                self.events['random_starvation'] += 1
        if number(obs.item.pre.ports['o_mem_req_valid']) and p['i_mem_req_ready'] == 0:
            self.events['request_stall'] += 1
            if obs.item.random:
                self.events['random_request_stall'] += 1
        if model.events['o_completed_with_error']:
            self.events['completed_with_error'] += 1

    def report(self):
        c = self.config
        errors = set(range(1, 22))
        if c.max_log2 == 0:
            errors -= {6, 7, 8}
        if c.max_log2 == (1 << c.aliases['ELEMENT_SIZE_WIDTH']) - 1:
            errors -= {5}
        if c.MAX_OUTSTANDING == 1 << c.aliases['TAG_WIDTH']:
            errors -= {12}
        if not c.check_internals:
            errors -= {11}
        required = ('start', 'stream', 'request', 'response', 'retire', 'finish', 'fail',
                    'memory_error', 'fatal', 'malformed', 'clear', 'reset', 'wrap',
                    'starvation', 'request_stall', 'completed_with_error',
                    'random_wrap', 'random_starvation', 'random_request_stall',
                    'malformed_when_full_and_blocked', 'final_error_included')
        goals = {key: self.events[key] > 0 for key in required}
        goals.update(
            every_mode_size=self.modes_sizes == {(m, s) for m in range(3) for s in range(c.max_log2 + 1)},
            every_occupancy=self.occupancies == set(range(c.MAX_OUTSTANDING + 1)),
            every_tag=self.tags == set(range(c.MAX_OUTSTANDING)),
            mode_stride_sign={(mode, field, sign) for mode, field in
                ((1, 'i_inner_stride'), (2, 'i_inner_stride'), (2, 'i_outer_stride'))
                for sign in ((-1, 0) if c.ADDR_WIDTH == 1 else (-1, 0, 1))} <= self.mode_signs,
            occupancy_transitions={'empty_to_nonempty', 'nonfull_to_full',
                                   'full_to_nonfull'} <= self.transitions,
            reset_engine_states={'idle', 'active', 'draining'} <= self.reset_states,
            stream_class_prior_writes={(code, owned) for code in range(16, 22)
                                      for owned in (False, True)} <= self.fault_classes_positions,
            every_fatal_class=errors <= self.errors,
            memory_error_positions={'first', 'middle', 'last'} <= self.memory_positions,
            all_stream_fault_fields={
                'i_stream_keep', 'i_stream_first', 'i_stream_last', 'i_stream_row_first',
                'i_stream_row_last', 'i_stream_end_of_stream', 'i_stream_channel_id',
                'i_stream_context_id', 'i_stream_error'} <= self.stream_fields,
            upstream_error_positions={'first', 'middle', 'last'} <= self.poison_positions,
            malformed_before_and_after_writes={'empty', 'owned'} <= self.fault_positions,
            random_campaign=self.random_transactions == c.random_cycles,
            ownership_accounting=self.accounting.get('outstanding') == 0 and
                self.accounting.get('accepted', -1) == self.accounting.get('retired', -2) +
                self.accounting.get('discarded', -3) == self.accounting.get('legal_beats', -4),
            actual_edge_observations=self.observations['edge'] > 0,
            completion_storage=not c.check_internals or min(self.storage_checks, self.gating_checks) > 0,
            optional_counters=not c.hdl_assertions or self.counter_checks > 0,
            counter_saturation=not c.hdl_assertions or self.saturated,
        )
        if c.MAX_OUTSTANDING > 1:
            goals['response_reordering'] = self.events['reordering'] > 0
            goals['random_reordering'] = self.events['random_reordering'] > 0
        if c.MAX_OUTSTANDING >= 3:
            goals['simultaneous_three_interfaces'] = self.events['three_transfers'] > 0
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
                    parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
                    accounting=self.accounting, random_transactions=self.random_transactions,
                    observations=dict(self.observations), occupancies=sorted(self.occupancies),
                    tags=sorted(self.tags), error_classes=sorted(self.errors),
                    modes_sizes=sorted(self.modes_sizes), stream_fault_fields=sorted(self.stream_fields),
                    memory_error_positions=sorted(self.memory_positions),
                    poison_positions=sorted(self.poison_positions),
                    crosses={name: dict(bins) for name, bins in self.crosses.items()},
                    transitions=sorted(self.transitions), reset_states=sorted(self.reset_states),
                    storage_checks=self.storage_checks, write_gate_checks=self.gating_checks,
                    counter_checks=self.counter_checks, saturated=self.saturated,
                    hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    external_checks=dict.fromkeys(('lint', 'formal', 'cdc', 'rdc', 'dft', 'vc_lp',
                        'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
