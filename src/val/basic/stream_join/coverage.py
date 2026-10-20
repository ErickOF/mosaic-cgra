"""Require atomicity, arrival-order, mask, stall and four-state operand coverage."""

from collections import Counter
from itertools import permutations, product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from stream_join.config import LONG_WAIT, STREAM_LENGTH
from stream_join.model import known, lane, required_inputs


class StreamJoinCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.controls, self.masks, self.final, self.population_final = set(), set(), set(), set()
        self.orders, self.permutations, self.mask_transitions = set(), set(), set()
        self.stalls, self.waits, self.acceptance_vectors = set(), set(), set()
        self.pattern_masks, self.data_bits, self.optional_valid, self.optional_data = set(), set(), set(), set()
        self.final_ready, self.ignored_mask, self.ignored_ready, self.clockless = set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.edge_items = self.maximum_stream = self.streaming = 0
        self.last_mask = None
        self.ledger = {}
        self.accepted_counts = [0]*self.config.inputs
        self.joined = 0
        self.clear_operation()

    def clear_operation(self):
        self.present = set()
        self.arrival_groups = []
        self.wait_length = self.stall_length = 0

    def arrivals(self, ports):
        c = self.config
        selected = required_inputs(c, ports)
        mask = sum(1 << k for k in selected)
        self.masks.add(mask)
        if self.last_mask is not None and mask != self.last_mask:
            self.mask_transitions.add((self.last_mask, mask))
        self.last_mask = mask
        present = {k for k in selected if ports['i_valid'][-k-1] == '1'}
        new = present-self.present
        if new:
            self.arrival_groups.append(tuple(sorted(new)))
            self.present.update(new)

    def edge(self, ports, accepted, joined, random):
        c = self.config
        selected = required_inputs(c, ports)
        mask = sum(1 << k for k in selected)
        population = len(selected)
        self.random_transactions += int(random)
        self.acceptance_vectors.add((joined, sum(1 << k for k in accepted)))
        self.streaming = self.streaming+1 if joined else 0
        self.maximum_stream = max(self.maximum_stream, self.streaming)
        if joined:
            self.joined += 1
            groups = tuple(self.arrival_groups)
            assert groups, 'Coverage saw consumption without any arrivals'
            flat = tuple(k for group in groups for k in group)
            kind = ('simultaneous' if len(groups) == 1 else 'forward' if all(len(g) == 1 for g in groups) and flat == tuple(sorted(selected))
                else 'reverse' if all(len(g) == 1 for g in groups) and flat == tuple(sorted(selected, reverse=True)) else 'mixed')
            self.orders.add((mask, kind))
            if all(len(group) == 1 for group in groups):
                self.permutations.add((mask, flat))
            if len(groups[-1]) == 1:
                self.final.update(groups[-1])
                self.population_final.update((population, k) for k in groups[-1])
            self.stalls.add((population, self.stall_length))
            self.waits.add((population, self.wait_length))
            for k in accepted:
                self.accepted_counts[k] += 1
                word = lane(ports['i_data'], k, c.width)
                self.pattern_masks.update((mask, name) for name in pattern_classes(word))
                for phase, data in (('input', word), ('output', lane(ports['o_data'], k, c.width))):
                    self.data_bits.update((phase, k, bit, state) for bit, state in enumerate(reversed(data)))
            self.clear_operation()
        elif ports['o_valid'] == '1':
            self.stall_length += 1
        elif self.present:
            self.wait_length += 1

    def observe(self, observation):
        c = self.config
        p, item, stage = observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        self.edge_items += int(stage == 'post' and item.edge)
        if stage != 'pre':
            return
        selected = required_inputs(c, p)
        mask = sum(1 << k for k in selected)
        if known(p['i_valid']) and known(p['i_ready']):
            self.controls.add((mask, int(p['i_valid'], 2), int(p['i_ready'])))
        missing = selected-{k for k in selected if p['i_valid'][-k-1] == '1'}
        if len(missing) == 1 and p['i_ready'] == '1':
            self.final_ready.update(missing)
        if not item.edge:
            self.clockless.add(int(p['o_valid']))
        if not known(p['i_ready']):
            self.ignored_ready.update(set(p['i_ready']))
        if not c.masked:
            self.ignored_mask.update((k, state) for k, state in enumerate(reversed(p['i_required'])) if state in 'xz')
        for k in set(range(c.inputs))-selected:
            self.optional_valid.add((k, p['i_valid'][-k-1]))
            self.optional_data.update((k, state) for state in lane(p['i_data'], k, c.width))

    def report(self):
        c = self.config
        masks = set(range(1, c.all_inputs+1)) if c.masked and c.inputs <= 5 else {c.all_inputs}
        populations = range(1, c.inputs+1) if c.masked else (c.inputs,)
        control_masks = range(c.all_inputs+1) if c.masked else (c.all_inputs,)
        expected_orders = {(mask, kind) for mask in masks for kind in ('simultaneous', 'forward', 'reverse', 'mixed')
            if kind == 'simultaneous' or mask.bit_count() >= (3 if kind == 'mixed' else 2)}
        expected_permutations = {(mask, order) for mask in masks for order in permutations(k for k in range(c.inputs) if mask & (1 << k))} if c.inputs <= 3 else set()
        goals = dict(
            exhaustive_small_control_matrix=(c.inputs > 5 or set(product(control_masks, range(c.all_inputs+1), (0, 1))) <= self.controls),
            every_small_nonzero_mask=masks <= self.masks,
            every_required_population=set(populations) <= {mask.bit_count() for mask in self.masks},
            idle_empty_mask=(not c.masked or 0 in self.masks),
            every_input_as_final_arrival=set(range(c.inputs)) <= self.final,
            population_final_arrival_cross=set(product(populations, range(c.inputs))) <= self.population_final,
            mask_arrival_order_cross=expected_orders <= self.orders,
            every_small_arrival_permutation=expected_permutations <= self.permutations,
            every_final_missing_input_ready=set(range(c.inputs)) <= self.final_ready,
            population_consumer_stall_cross=set(product(populations, (1, LONG_WAIT))) <= self.stalls,
            population_producer_wait_cross=set(product((p for p in populations if p > 1), (1, LONG_WAIT))) <= self.waits,
            continuous_join_stream=self.maximum_stream >= STREAM_LENGTH,
            optional_valid_activity=(not c.masked or set(product(range(c.inputs), '01xz')) <= self.optional_valid),
            optional_data_activity=(not c.masked or set(product(range(c.inputs), '01xz')) <= self.optional_data),
            disabled_mask_ignored=(c.masked or set(product(range(c.inputs), 'xz')) <= self.ignored_mask),
            irrelevant_downstream_unknowns=((not c.masked and c.inputs == 1) or {'x', 'z'} <= self.ignored_ready),
            idle_mask_transitions=(not c.masked or bool(self.mask_transitions)),
            zero_cycle_clockless_changes={0, 1} <= self.clockless,
            pattern_mask_cross=set(product(masks, ('zero', 'one', 'alternating', 'walking_one', 'walking_zero'))) <= self.pattern_masks,
            every_bit_of_each_operand=set(product(('input', 'output'), range(c.inputs), range(c.width), '01xz')) <= self.data_bits,
            acceptance_vector_cross=({(False, 0)} | {(True, mask) for mask in masks}) <= self.acceptance_vectors,
            atomic_operand_ledger=(bool(self.ledger) and self.ledger['joined'] > 0 and not any(self.ledger['pending'])
                and self.ledger['accepted'] == self.accepted_counts and self.ledger['joined'] == self.joined),
            randomized_campaign=self.random_transactions == c.random_cycles,
            all_sampling_stages=(self.observations['pre'] == self.observations['post'] == self.observations['held']
                and self.observations['edge'] == self.edge_items and self.edge_items > 0))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_parameters else 'NOT_RUN', token_ledger=self.ledger,
            control_bins=sorted(self.controls), required_masks=sorted(self.masks), final_arrivals=sorted(self.final),
            population_final_bins=sorted(self.population_final), mask_order_bins=sorted(self.orders),
            permutation_bins=sorted(self.permutations), stall_bins=sorted(self.stalls), wait_bins=sorted(self.waits),
            maximum_stream=self.maximum_stream, optional_valid_bins=sorted(self.optional_valid),
            optional_data_bins=sorted(self.optional_data), ignored_mask_bins=sorted(self.ignored_mask),
            mask_transitions=sorted(self.mask_transitions), pattern_mask_bins=sorted(self.pattern_masks),
            data_bit_bins=sorted(self.data_bits), waveform_transitions=dict(self.transitions))
