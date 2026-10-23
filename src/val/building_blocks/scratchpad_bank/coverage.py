"""Checked occupancy, byte placement, hazards, protection and cancellation goals."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from scratchpad_bank.model import number


class ScratchpadBankCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.crosses = {}
        self.occupancies = {0}
        self.operations_sizes_offsets = set()
        self.errors = set()
        self.single_faults = set()
        self.reset_states = set()
        self.flush_states = set()
        self.addresses = set()
        self.storage_checks = self.memory_checks = self.backend_checks = self.random_transactions = 0
        self.accounting = {}
        self.counter_checks = 0
        self.saturated = False
        self.previous_request = None

    def cross(self, name, *values):
        self.crosses.setdefault(name, Counter())[str(tuple(values))] += 1

    def fault_observed(self, mask, state):
        if not state and mask.bit_count() == 1:
            self.single_faults.add(mask.bit_length() - 1)
        self.events['injected_fault'] += 1
        self.cross('injected_fault', mask.bit_count(), state or 'flip')

    def reset_observed(self, model):
        state = 'work' if model.work else 'pending' if model.pending else 'idle'
        self.reset_states.add(state)
        self.cross('reset_state', self.config.ASYNC_RESET, state)

    def record(self, obs, model, q):
        c, p = self.config, q['p']
        self.random_transactions += int(obs.item.random)
        self.occupancies.add(len(model.pending))
        self.accounting = dict(accepted=model.total_in, emitted=model.total_out,
                               discarded=model.discarded, outstanding=len(model.pending))
        if not obs.item.edge or not q['run']:
            return
        for name in ('accept', 'consume', 'capture', 'commit', 'corrected', 'uncorrectable', 'scrub'):
            self.events[name] += int(q[name])
        if q['accept']:
            e = q['entry']
            if e['slot'] == c.MAX_OUTSTANDING - 1:
                self.events['wrap'] += 1
                self.events['random_wrap'] += int(obs.item.random)
            self.cross('occupancy_transfers', q['occupancy'], q['accept'], q['consume'])
            if e['error']:
                self.errors.add(e['error'])
                self.cross('illegal_operation', e['error'], e['write'])
            else:
                self.addresses.add(e['word'])
                self.operations_sizes_offsets.add((e['write'], e['size'], e['offset']))
                self.cross('operation_size_offset', e['write'], e['size'], e['offset'])
                self.events['zero_strobe'] += int(e['write'] and not e['mask'])
                self.events['rmw'] += int(e['rmw'])
                self.events['partial'] += int(e['write'] and e['mask'] not in (0, (1 << c.bytes) - 1))
                self.cross('strobe_offset', e['mask'].bit_count(), e['offset'])
                if self.previous_request and self.previous_request['word'] == e['word']:
                    self.cross('same_address_hazard', self.previous_request['write'], e['write'], c.BACKEND_READ_LATENCY)
                self.previous_request = e
                if obs.item.random:
                    self.events['random_read' if not e['write'] else 'random_write'] += 1
        if q['consume'] and q['accept']:
            self.events['simultaneous'] += 1
        if q['result']:
            r = q['result']
            self.cross('protection_response', c.PROTECTION_MODE, r['o_rsp_error_code'],
                       r['o_rsp_corrected'], r['o_rsp_uncorrectable'])
            if q['work'] == 'wait' and r['o_rsp_write']:
                self.cross('rmw_old_status', r['o_rsp_error_code'], r['o_rsp_corrected'])
        stall = obs.item.pre.ports['o_rsp_valid'] == '1' and p['i_rsp_ready'] == 0
        blocked = p['i_req_valid'] == 1 and obs.item.pre.ports['o_req_ready'] == '0'
        self.events['response_stall'] += int(stall)
        self.events['request_stall'] += int(blocked)
        self.events['full'] += int(q['occupancy'] == c.MAX_OUTSTANDING)
        self.events['work_stall'] += int(blocked and q['work'] is not None)
        if obs.item.random:
            self.events['random_response_stall'] += int(stall)
            self.events['random_fault'] += int(bool(obs.item.fault))
        if q['flushing']:
            state = q['work'] or ('pending' if q['occupancy'] else 'idle')
            self.flush_states.add(state)
            self.cross('flush_occupancy_work', q['occupancy'], state)
            self.events['flush'] += 1
        if obs.item.protocol:
            self.events['protocol_fault'] += 1

    def report(self):
        c = self.config
        required_errors = {1}
        if c.DEPTH_WORDS * c.bytes != 1 << c.aliases['A']:
            required_errors.add(2)
        if c.byte_log < (1 << c.aliases['S']) - 1:
            required_errors.add(3)
        if c.bytes >= 4:
            required_errors.add(4)
        if c.bytes >= 2:
            required_errors |= {5, 6}
        expected_accesses = {(op, 1 << size, offset) for op in (False, True)
                             for size in range(c.byte_log + 1)
                             for offset in range(0, c.bytes, 1 << size)}
        goals = {name: self.events[name] > 0 for name in (
            'accept', 'consume', 'capture', 'wrap', 'zero_strobe', 'response_stall',
            'request_stall', 'full', 'flush', 'random_wrap', 'random_read', 'random_write',
            'random_response_stall')}
        goals.update(every_size_offset=expected_accesses <= self.operations_sizes_offsets,
                     every_occupancy=self.occupancies == set(range(c.MAX_OUTSTANDING + 1)),
                     every_address=self.addresses == set(range(c.DEPTH_WORDS)),
                     illegal_classes=required_errors <= self.errors,
                     reset_states={'idle', 'pending'} <= self.reset_states,
                     flush_states={'idle', 'pending'} <= self.flush_states,
                     ownership_accounting=self.accounting.get('outstanding') == 0 and
                         self.accounting.get('accepted', -1) == self.accounting.get('emitted', -2) + self.accounting.get('discarded', -3),
                     random_campaign=self.random_transactions == c.random_cycles,
                     actual_edges=self.observations['edge'] > 0,
                     storage_backend=not c.check_internals or min(self.storage_checks, self.memory_checks, self.backend_checks) > 0)
        goals['optional_counters'] = not c.instrumentation or self.counter_checks > 0
        goals['counter_saturation'] = not c.instrumentation or self.saturated
        if c.MAX_OUTSTANDING > 1:
            goals['simultaneous_allocate_retire'] = self.events['simultaneous'] > 0
        if c.bytes > 1:
            goals['partial_write'] = self.events['partial'] > 0
        if c.check_internals:
            goals.update(every_fault_bit=self.single_faults == set(range(c.stored_width)),
                         protocol_fault=self.events['protocol_fault'] > 0,
                         random_fault=self.events['random_fault'] > 0)
        if c.PROTECTION_MODE:
            goals['protection_failure'] = self.events['uncorrectable'] > 0
        if c.bytes > 1 and (c.PROTECTION_MODE == 2 or c.PROTECTION_MODE == 1 and c.PARITY_GRANULARITY > 8):
            goals.update(atomic_rmw=self.events['rmw'] > 0,
                         work_stalls=self.events['work_stall'] > 0,
                         flush_wait_commit={'wait', 'commit'} <= self.flush_states)
        if c.PROTECTION_MODE == 2:
            goals['correction'] = self.events['corrected'] > 0
            goals['scrub_policy'] = (self.events['scrub'] > 0) == bool(c.SCRUB_ON_CORRECT)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
                    parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
                    accounting=self.accounting, random_transactions=self.random_transactions,
                    occupancies=sorted(self.occupancies), error_classes=sorted(self.errors),
                    single_fault_bits=sorted(self.single_faults), observations=dict(self.observations),
                    reset_states=sorted(self.reset_states), flush_states=sorted(self.flush_states),
                    storage_checks=self.storage_checks, memory_checks=self.memory_checks,
                    backend_checks=self.backend_checks, counter_checks=self.counter_checks,
                    counter_saturation=self.saturated, crosses={n: dict(v) for n, v in self.crosses.items()},
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    external_checks=dict.fromkeys(('lint', 'formal', 'cdc', 'rdc', 'dft', 'vc_lp',
                        'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
