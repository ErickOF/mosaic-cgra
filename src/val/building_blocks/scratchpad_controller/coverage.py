"""Coverage goals are measured from checked interfaces and obligations."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from scratchpad_controller.model import unpack


class ControllerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.crosses = {}
        self.addresses = set()
        self.errors = set()
        self.malformed = set()
        self.occupancies = set()
        self.clients_banks_ops = set()
        self.accesses = set()
        self.contenders = set()
        self.capture_checks = self.storage_checks = self.random_transactions = 0
        self.accounting = {}
        self.counter_checks = 0
        self.saturated = False

    def cross(self, name, *values):
        self.crosses.setdefault(name, Counter())[str(values)] += 1

    def record(self, item, model, q):
        if not item.edge:
            return
        c = self.config
        self.random_transactions += int(item.random)
        self.occupancies.update(map(len, model.queues))
        if not q['run']:
            self.events['reset'] += 1
            return
        for n in q['allocations']:
            e = q['reqs'][n]
            self.events['accept'] += 1
            self.events['local'] += int(q['errors'][n] != 0)
            if item.random:
                self.events['random_accept'] += 1
                self.events['random_permission_denial'] += int(q['errors'][n] == 10)
                self.events['random_structural_error'] += int(q['errors'][n] in range(1, 7))
            self.events['wrap'] += int(model.issue[n] == c.MAX_OUTSTANDING_PER_CLIENT - 1)
            if q['errors'][n]:
                self.errors.add(q['errors'][n])
            else:
                self.addresses.add(e['address'])
                self.clients_banks_ops.add((n, q['mapped'][n][0], e['write']))
                self.accesses.add((e['write'], e['size_log2'], e['address'] % c.bytes))
            self.cross('client_bank_operation', n, q['mapped'][n][0], e['write'], q['errors'][n])
            self.cross('tag_slot', e['tag'], model.issue[n])
            self.events['simultaneous'] += int(n in q['retirements'])
        self.events['retire'] += len(q['retirements'])
        self.events['parallel'] += int(len(q['bank_accept']) > 1)
        for b, candidates in enumerate(q['candidates']):
            self.contenders.add((b, len(candidates)))
            self.cross('contenders_winner', b, len(candidates), q['selected'][b], b in q['bank_accept'])
        self.events['conflict'] += int(any(len(v) > 1 for v in q['candidates']))
        self.events['grant_stall'] += int(any(q['bank_requests'][b] is not None and b not in q['bank_accept'] for b in range(c.NUM_BANKS)))
        self.events['response_stall'] += int(any(e is not None and n not in q['retirements'] for n, e in enumerate(q['client_responses'])))
        self.events['full'] += int(any(len(v) == c.MAX_OUTSTANDING_PER_CLIENT for v in model.queues))
        self.events['permission_update'] += int(q['perm_accept'])
        self.events['random_permission_update'] += int(item.random and q['perm_accept'])
        self.events['flush'] += int(q['start'])
        self.events['flush_wait'] += int(model.flushing)
        for n, b in enumerate(q['collections']):
            if b is not None:
                e = q['entry'][b]
                self.events['reorder'] += int(model.queues[n][0] is not e)
                self.events['collector_conflict'] += int(sum(t == n for t in q['targets']) > 1)
                self.cross('reliability', b, n, q['rsps'][b]['error_code'], q['rsps'][b]['corrected'])
                self.events['corrected'] += int(q['rsps'][b]['corrected'] == 1)
                self.events['random_corrected'] += int(item.random and q['rsps'][b]['corrected'] == 1)
                self.events['random_uncorrectable'] += int(item.random and q['rsps'][b]['uncorrectable'] == 1)
                self.events['uncorrectable'] += int(q['rsps'][b]['uncorrectable'] == 1)
        for b in q['bank_collect']:
            if q['malformed'][b]:
                self.malformed.add(q['malformed'][b])
                self.cross('malformed', b, q['malformed'][b])

    def report(self):
        c = self.config
        goals = {n: self.events[n] > 0 for n in ('accept', 'retire', 'wrap', 'grant_stall',
                    'response_stall', 'full', 'flush', 'reset')}
        goals.update(client_bank_operations=self.clients_banks_ops == {
            (n, b, op) for n in range(c.NUM_CLIENTS) for b in range(c.NUM_BANKS) for op in (0, 1)},
            every_size_offset={(op, size, offset) for op in (0, 1) for size in range(c.bytes.bit_length())
                for offset in range(0, c.bytes, 1 << size)} <= self.accesses,
            contender_populations={(b, n) for b in range(c.NUM_BANKS)
                for n in range(1, c.NUM_CLIENTS + 1)} <= self.contenders)
        goals.update(capture_checks=self.capture_checks > 0, storage_checks=self.storage_checks > 0,
                     random_campaign=self.random_transactions == c.random_cycles,
                     actual_edges=self.observations['edge'] > 0)
        if c.instrumentation:
            goals['optional_counters'] = self.counter_checks > 0 and self.saturated
            goals['counter_controls'] = self.events['counter_clear'] > 0 and self.events['counter_disabled'] > 0
        if c.integration and c.protection:
            goals['physical_faults'] = self.events['physical_fault'] > 0 and self.events['uncorrectable'] > 0
            if c.protection == 2:
                goals['physical_correction'] = self.events['corrected'] > 0
        if not c.integration:
            goals['malformed'] = {1, 4, 5, 7, 8} <= self.malformed
            if c.NUM_BANKS > 1:
                goals['wrong_bank'] = 6 in self.malformed
            if c.NUM_CLIENTS != 2 ** max(1, (c.NUM_CLIENTS - 1).bit_length()):
                goals['invalid_client'] = 2 in self.malformed
            if c.MAX_OUTSTANDING_PER_CLIENT != 2 ** c.slot_width:
                goals['invalid_slot'] = 3 in self.malformed
            goals['reliability'] = self.events['corrected'] > 0 and self.events['uncorrectable'] > 0
            if c.capacity <= 2048:
                goals['exhaustive_mapping'] = self.addresses == set(range(c.capacity))
        if c.ENFORCE_PERMISSIONS:
            goals['permissions'] = self.events['permission_update'] > 0 and 10 in self.errors
        if c.NUM_CLIENTS > 1:
            goals['contention'] = self.events['conflict'] > 0
        if c.NUM_BANKS > 1 and c.NUM_CLIENTS > 1:
            goals['parallel'] = self.events['parallel'] > 0
        if not c.integration and c.NUM_BANKS > 1 and c.MAX_OUTSTANDING_PER_CLIENT > 1:
            goals['reordering'] = self.events['reorder'] > 0
            goals['collector_contention'] = self.events['collector_conflict'] > 0
        required = {1, 5, 6} if c.bytes > 1 else {1}
        if c.bytes >= 4:
            required.add(4)
        if c.capacity != 1 << c.aliases['A']:
            required.add(2)
        if c.bytes.bit_length() - 1 < (1 << c.aliases['S']) - 1:
            required.add(3)
        goals['structural_errors'] = required <= self.errors
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, integration=c.integration, protection=c.protection,
            goals=goals, events=dict(self.events), observations=dict(self.observations),
            accounting=self.accounting, random_transactions=self.random_transactions,
            mapped_bytes=len(self.addresses), malformed_classes=sorted(self.malformed),
            local_errors=sorted(self.errors), occupancies=sorted(self.occupancies),
            capture_checks=self.capture_checks, storage_checks=self.storage_checks,
            counter_checks=self.counter_checks, counter_saturation=self.saturated,
            crosses={n: dict(v) for n, v in self.crosses.items()},
            external_checks=dict.fromkeys(('lint', 'formal', 'cdc', 'rdc', 'dft', 'vc_lp',
                'synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
