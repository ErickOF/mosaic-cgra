"""Require address, port, collision timing, concurrency and data-pattern coverage."""

from collections import Counter
from itertools import combinations, product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from register_file.model import legal_writes
from register_file.transaction import fields, known


class RegisterFileCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.reads, self.writes, self.relations, self.read_pairs = set(), Counter(), set(), set()
        self.read_counts, self.write_counts, self.enables, self.distances = set(), set(), set(), set()
        self.initialization, self.patterns, self.walking, self.ignored = set(), set(), set(), set()
        self.four_state, self.transitions, self.observations = set(), Counter(), Counter()
        self.random_transactions = self.edges = self.no_edge_writes = 0

    def record_writes(self, observation, model):
        c, p = self.config, observation.ports
        writes = legal_writes(c, p)
        self.edges += 1
        self.random_transactions += int(observation.item.random)
        self.write_counts.add(len(writes))
        for w, address, data in writes:
            self.writes[w, address] += 1
            self.patterns.update(('write', w, name) for name in pattern_classes(data))
            if known(data):
                self.walking.update((w, bit, state) for bit in range(c.width) for state in (0, 1)
                    if data == ''.join(str(state if index == bit else 1-state) for index in reversed(range(c.width))))
        self.distances.update(abs(a-b) for (_, a, _), (_, b, _) in combinations(writes, 2))

    def sample(self, observation, model):
        c, p, item, stage = self.config, observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        if stage != 'pre':
            return
        # Write enables are checked at the actual write edge. Preserve X/Z
        # until that assertion runs instead of coercing them into coverage bins.
        if not known(p['i_write_enable']):
            return
        re, we = int(p['i_read_enable'], 2), int(p['i_write_enable'], 2)
        self.read_counts.add(re.bit_count())
        self.enables.add((re, we))
        writes = legal_writes(c, p)
        self.no_edge_writes += int(not item.edge and bool(writes))
        addresses = fields(p['i_read_address'], c.address_width)
        for r, address in enumerate(addresses):
            if re & (1 << r):
                value = int(address, 2)
                self.reads.add((r, value))
                word = model.words[value]
                self.initialization.add((r, word is not None))
                if word is not None:
                    self.patterns.update(('read', r, name) for name in pattern_classes(word))
                    self.four_state.update((r, state) for state in 'xz' if state in word)
                if item.edge:
                    self.relations.update((r, w, 'same' if value == target else 'different') for w, target, _ in writes)
        self.read_pairs.update((a, b, 'same' if addresses[a] == addresses[b] else 'different')
            for a, b in combinations(range(c.read_ports), 2) if re & (1 << a) and re & (1 << b))
        for kind, count, width in (('read_address', c.read_ports, c.address_width),
                ('write_address', c.write_ports, c.address_width), ('write_data', c.write_ports, c.width)):
            enables = re if kind.startswith('read') else we
            for port, word in enumerate(fields(p['i_' + kind], width)):
                if not enables & (1 << port):
                    self.ignored.update((kind, port, bit, state) for bit, state in enumerate(reversed(word)) if state in 'xz')

    def report(self):
        c = self.config
        expected_patterns = {'zero', 'one', 'alternating', 'walking_one', 'walking_zero'}
        relations = ('same', 'different') if c.depth > 1 else ('same',)
        write_masks = {mask for mask in range(1 << c.write_ports) if mask.bit_count() <= c.depth}
        goals = dict(
            every_read_port_address=set(product(range(c.read_ports), range(c.depth))) <= self.reads,
            every_write_port_address=set(product(range(c.write_ports), range(c.depth))) <= self.writes.keys(),
            every_port_address_rewritten=all(self.writes[w, a] >= 2 for w in range(c.write_ports) for a in range(c.depth)),
            every_read_concurrency=set(range(c.read_ports+1)) <= self.read_counts,
            every_feasible_write_concurrency=set(range(min(c.write_ports, c.depth)+1)) <= self.write_counts,
            read_write_enable_cross=set(product(range(1 << c.read_ports), write_masks)) <= self.enables,
            read_pair_address_relations={(a, b, relation) for a, b in combinations(range(c.read_ports), 2)
                for relation in relations} <= self.read_pairs,
            every_read_write_port_relation=set(product(range(c.read_ports), range(c.write_ports), relations)) <= self.relations,
            every_two_write_address_distance=(set(range(1, c.depth)) <= self.distances if c.write_ports > 1 else True),
            initialized_and_uninitialized_reads=set(product(range(c.read_ports), (False, True))) <= self.initialization,
            every_port_data_pattern=({('read', r, pattern) for r in range(c.read_ports) for pattern in expected_patterns}
                | {('write', w, pattern) for w in range(c.write_ports) for pattern in expected_patterns}) <= self.patterns,
            every_write_port_walking_bit=set(product(range(c.write_ports), range(c.width), (0, 1))) <= self.walking,
            intentional_four_state_transport=set(product(range(c.read_ports), 'xz')) <= self.four_state,
            disabled_unknown_inputs=({(kind, port, bit, state) for kind, count, width in
                (('read_address', c.read_ports, c.address_width), ('write_address', c.write_ports, c.address_width),
                 ('write_data', c.write_ports, c.width)) for port in range(count) for bit in range(width) for state in 'xz'}) <= self.ignored,
            active_writes_without_edge_hold=self.no_edge_writes > 0,
            randomized_campaign=self.random_transactions == c.random_cycles,
            all_sampling_stages=(self.observations['pre'] == self.observations['post'] == self.observations['held']
                and self.observations['edge'] == self.edges and self.edges > 0))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            read_port_address_bins=sorted(self.reads), write_port_address_bins=sorted(self.writes),
            read_write_relation_bins=sorted(self.relations), read_pair_bins=sorted(self.read_pairs),
            enable_cross_bins=sorted(self.enables), write_distances=sorted(self.distances),
            data_pattern_bins=sorted(self.patterns), walking_bit_bins=sorted(self.walking),
            ignored_unknown_bins=sorted(self.ignored), intentional_unknown_read_bins=sorted(self.four_state),
            waveform_transitions=dict(self.transitions), active_no_edge_writes=self.no_edge_writes,
            coverage_limits=dict(distinct_reads='Unreachable at depth one' if c.depth == 1 else 'applicable',
                concurrent_writes=f'At most min(DEPTH, NUM_WRITE_PORTS) = {min(c.depth, c.write_ports)} legal writes',
                initialization='Unwritten content is unspecified; no deterministic value is claimed'))
