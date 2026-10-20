"""Require port/entry/lane/slice access, mask/broadcast and collision coverage."""

from collections import Counter
from itertools import combinations, product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from vector_register_file.model import legal_writes, write_violation
from vector_register_file.transaction import fields, known


def mask_classes(config, mask):
    classes = set()
    if mask == (1 << config.mask_width)-1:
        classes.add('full')
    if mask.bit_count() == 1:
        classes.add('single')
    populations = [((mask >> (lane*config.slices_per_lane)) & ((1 << config.slices_per_lane)-1)).bit_count()
        for lane in range(config.lanes)]
    if mask and all(count in (0, config.slices_per_lane) for count in populations):
        classes.add('lane')
    if any(0 < count < config.slices_per_lane for count in populations):
        classes.add('partial')
    if mask and mask in (sum(1 << bit for bit in range(0, config.mask_width, 2)),
            sum(1 << bit for bit in range(1, config.mask_width, 2))):
        classes.add('alternating')
    return classes


class VectorRegisterFileCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.reads, self.writes, self.relations, self.read_pairs = set(), Counter(), set(), set()
        self.lane_populations, self.lane_masks, self.write_populations, self.single_slices = set(), set(), set(), set()
        self.concurrency, self.write_pairs, self.initialization = set(), set(), set()
        self.patterns, self.data_bits, self.ignored, self.broadcast_ignored, self.disabled_broadcast = set(), set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.edges = self.random_transactions = self.no_edge_writes = self.write_events = 0

    def record_writes(self, observation, model):
        c, p = self.config, observation.ports
        self.edges += 1
        self.random_transactions += int(observation.item.random)
        if write_violation(c, p, observation.item.four_state_data) is not None:
            return
        writes = legal_writes(c, p)
        self.write_events += len(writes)
        for write in writes:
            mask = sum(1 << s for s in write.slices)
            classes = mask_classes(c, mask)
            if len(write.slices) == 1:
                self.single_slices.add((write.port, next(iter(write.slices)), int(write.broadcast)))
            for s, data in write.slices.items():
                self.writes[write.port, write.address, s] += 1
                self.patterns.update((write.port, kind, name) for kind in classes for name in pattern_classes(data))
                self.data_bits.update(('write', write.port, s, bit, state) for bit, state in enumerate(reversed(data)))
        for a, b in combinations(writes, 2):
            self.write_pairs.add((a.port, b.port, 'disjoint' if a.address == b.address else 'different'))

    def sample(self, observation, model):
        c, p, item, stage = self.config, observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        if stage not in ('pre', 'post'):
            return
        lanes = fields(p['i_read_lane_enable'], c.lanes)
        addresses = fields(p['i_read_address'], c.address_width)
        active = {}
        for r, address in enumerate(addresses):
            enable = int(p['i_read_enable'][-r-1])
            if known(lanes[r]):
                self.lane_populations.add((r, int(lanes[r], 2).bit_count(), enable))
                if enable:
                    self.lane_masks.add((r, int(lanes[r], 2)))
            if enable and '1' in lanes[r]:
                value = int(address, 2)
                active[r] = value
                for s in range(c.mask_width):
                    if lanes[r][-(s//c.slices_per_lane)-1] == '1':
                        self.reads.add((r, value, s))
                        word = model.slices[value][s]
                        self.initialization.add((r, word is not None))
                        if word is not None:
                            self.data_bits.update(('read', r, s, bit, state) for bit, state in enumerate(reversed(word)))
            if stage == 'pre':
                if not enable:
                    self.ignored.update(('disabled_read', r, state) for state in address+lanes[r] if state in 'xz')
                elif lanes[r] == '0'*c.lanes:
                    self.ignored.update(('zero_lanes', r, state) for state in address if state in 'xz')
        if stage != 'pre' or not known(p['i_write_enable']):
            return
        writes = legal_writes(c, p)
        self.no_edge_writes += int(not item.edge and bool(writes))
        if item.edge:
            self.relations.update((r, write.port, 'same' if address == write.address else 'different')
                for r, address in active.items() for write in writes)
        self.read_pairs.update((a, b, 'same' if active[a] == active[b] else 'different') for a, b in combinations(sorted(active), 2))
        masks = fields(p['i_write_mask'], c.mask_width)
        write_addresses = fields(p['i_write_address'], c.address_width)
        vectors = fields(p['i_write_data'], c.width)
        if known(p['i_read_enable']):
            self.concurrency.add((int(p['i_read_enable'], 2), int(p['i_write_enable'], 2)))
        for w, mask in enumerate(masks):
            enabled = p['i_write_enable'][-w-1] == '1'
            broadcast = p['i_write_broadcast'][-w-1]
            if enabled and known(mask) and (broadcast in '01' or not c.broadcast):
                self.write_populations.add((w, int(mask, 2).bit_count(), int(broadcast) if c.broadcast else 0))
            if not enabled or mask == '0'*c.mask_width:
                kind = 'disabled_write' if not enabled else 'zero_mask'
                self.ignored.update((kind, w, state) for state in write_addresses[w]+vectors[w]+broadcast if state in 'xz')
            elif known(mask):
                if not c.broadcast:
                    self.disabled_broadcast.update((w, state) for state in broadcast if state in 'xz')
                if c.broadcast and broadcast == '1':
                    for lane, word in enumerate(fields(vectors[w], c.lane_width)):
                        if lane:
                            self.broadcast_ignored.update((w, lane, state) for state in word if state in 'xz')
                else:
                    for s, word in enumerate(fields(vectors[w], c.slice_width)):
                        if mask[-s-1] == '0':
                            self.ignored.update(('unmasked_data', w, state) for state in word if state in 'xz')

    def report(self):
        c = self.config
        modes = (0, 1) if c.broadcast else (0,)
        relations = ('same', 'different') if c.depth > 1 else ('same',)
        kinds = {'full', 'lane', 'single', 'alternating'} | ({'partial'} if c.slices_per_lane > 1 else set())
        patterns = {'zero', 'one', 'alternating', 'walking_one', 'walking_zero'}
        feasible_writes = {we for we in range(1 << c.write_ports) if we.bit_count() <= c.depth*c.mask_width}
        pairs = set(combinations(range(c.write_ports), 2))
        goals = dict(
            every_read_port_entry_slice=set(product(range(c.read_ports), range(c.depth), range(c.mask_width))) <= self.reads,
            every_write_port_entry_slice=set(product(range(c.write_ports), range(c.depth), range(c.mask_width))) <= self.writes.keys(),
            read_lane_population_activity_cross=set(product(range(c.read_ports), range(c.lanes+1), (0, 1))) <= self.lane_populations,
            individual_read_lanes={(r, mask) for r in range(c.read_ports) for lane in range(c.lanes)
                for mask in (1 << lane, ((1 << c.lanes)-1) ^ (1 << lane))} <= self.lane_masks,
            write_population_broadcast_cross=set(product(range(c.write_ports), range(c.mask_width+1), modes)) <= self.write_populations,
            every_individual_slice_mode=set(product(range(c.write_ports), range(c.mask_width), modes)) <= self.single_slices,
            read_write_enable_cross=set(product(range(1 << c.read_ports), feasible_writes)) <= self.concurrency,
            every_read_write_relation=set(product(range(c.read_ports), range(c.write_ports), relations)) <= self.relations,
            read_pair_relations={(a, b, relation) for a, b in combinations(range(c.read_ports), 2) for relation in relations} <= self.read_pairs,
            simultaneous_distinct_entries=(c.depth == 1 or {(a, b, 'different') for a, b in pairs} <= self.write_pairs),
            same_entry_disjoint_merge=(c.mask_width == 1 or {(a, b, 'disjoint') for a, b in pairs} <= self.write_pairs),
            initialized_and_uninitialized_reads=set(product(range(c.read_ports), (False, True))) <= self.initialization,
            pattern_mask_cross=set(product(range(c.write_ports), kinds, patterns)) <= self.patterns,
            every_written_slice_bit=set(product(('write',), range(c.write_ports), range(c.mask_width), range(c.slice_width), '01xz')) <= self.data_bits,
            every_read_slice_bit=set(product(('read',), range(c.read_ports), range(c.mask_width), range(c.slice_width), '01xz')) <= self.data_bits,
            disabled_read_and_zero_lane_unknowns=({(kind, r, state) for kind in ('disabled_read', 'zero_lanes') for r in range(c.read_ports) for state in 'xz'}) <= self.ignored,
            disabled_write_and_zero_mask_unknowns=({(kind, w, state) for kind in ('disabled_write', 'zero_mask') for w in range(c.write_ports) for state in 'xz'}) <= self.ignored,
            unmasked_unknown_data=(c.mask_width == 1 or {('unmasked_data', w, state) for w in range(c.write_ports) for state in 'xz'} <= self.ignored),
            broadcast_ignored_source_lanes=(not c.broadcast or set(product(range(c.write_ports), range(1, c.lanes), 'xz')) <= self.broadcast_ignored),
            disabled_broadcast_ignored=(c.broadcast or set(product(range(c.write_ports), 'xz')) <= self.disabled_broadcast),
            writes_without_edges_hold=self.no_edge_writes > 0,
            randomized_campaign=self.random_transactions == c.random_cycles,
            all_sampling_stages=(self.observations['pre'] == self.observations['post'] == self.observations['held']
                and self.observations['edge'] == self.edges and self.edges > 0))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            read_bins=sorted(self.reads), write_bins=sorted(self.writes), slice_updates=sum(self.writes.values()),
            active_write_events=self.write_events, lane_population_bins=sorted(self.lane_populations),
            lane_mask_bins=sorted(self.lane_masks), write_population_bins=sorted(self.write_populations),
            singleton_bins=sorted(self.single_slices), concurrency_bins=sorted(self.concurrency),
            read_write_relation_bins=sorted(self.relations), read_pair_bins=sorted(self.read_pairs),
            write_pair_bins=sorted(self.write_pairs), initialization_bins=sorted(self.initialization),
            pattern_mask_bins=sorted(self.patterns), data_bit_bins=sorted(self.data_bits),
            ignored_bins=sorted(self.ignored), broadcast_ignored_bins=sorted(self.broadcast_ignored),
            disabled_broadcast_bins=sorted(self.disabled_broadcast), waveform_transitions=dict(self.transitions))
