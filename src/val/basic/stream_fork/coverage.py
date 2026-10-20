"""Require per-destination delivery, completion-order, reset and payload coverage."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from stream_fork.config import LONG_STALL, STREAM_LENGTH
from stream_fork.model import lane


class StreamForkCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.masks, self.first, self.final, self.population_final = set(), set(), set(), set()
        self.mask_orders, self.pending_ready, self.pattern_masks = set(), set(), set()
        self.data_bits, self.ignored_ready, self.ignored_data = set(), set(), set()
        self.reset_populations, self.reset_pulses, self.clockless = set(), set(), set()
        self.stalls, self.tail_stalls, self.completions, self.accept_completion = set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.ledger = []
        self.random_transactions = self.edge_items = self.maximum_stream = self.long_idle = 0
        self.producer_stalls = self.maximum_producer_stall = 0
        self.reset_epoch()

    def reset_epoch(self):
        self.streaming = self.idle = 0
        self.lane_stalls = [0]*self.config.outputs
        self.tail_lengths = [0]*self.config.outputs

    def record(self, event, ports):
        c = self.config
        pending, popped = event['before'], event['popped']
        population = pending.bit_count()
        ready_class = 'all' if len(popped) == population else 'some' if popped else 'none'
        self.pending_ready.add((population, ready_class))
        self.accept_completion.add((event['push'], event['complete']))
        self.streaming = self.streaming+1 if event['push'] and event['complete'] else 0
        self.maximum_stream = max(self.maximum_stream, self.streaming)
        self.idle = self.idle+1 if not pending and not event['push'] else 0
        self.long_idle = max(self.long_idle, self.idle)
        if ports['i_valid'] == '1' and ports['o_ready'] == '0':
            self.producer_stalls += 1
            self.maximum_producer_stall = max(self.maximum_producer_stall, self.producer_stalls)
        else:
            self.producer_stalls = 0
        if event['push']:
            mask = event['destination']
            self.masks.add(mask)
            self.pattern_masks.update((mask, name) for name in pattern_classes(event['data']))
            self.data_bits.update((-1, bit, state) for bit, state in enumerate(reversed(event['data'])))
        if event['complete']:
            order, selection = event['order'], event['selection']
            self.first.update(order[0])
            self.final.update(order[-1])
            self.population_final.update((selection.bit_count(), k) for k in order[-1])
            kind = 'simultaneous' if len(order) == 1 else 'staggered'
            self.mask_orders.add((selection, kind))
            self.completions.add((kind, event['push']))
        for k in range(c.outputs):
            if k in popped:
                self.stalls.add((k, self.lane_stalls[k]))
                self.tail_stalls.add((k, self.tail_lengths[k]))
                self.lane_stalls[k] = 0
                self.tail_lengths[k] = 0
                self.data_bits.update((k, bit, state) for bit, state in enumerate(reversed(lane(ports['o_data'], k, c.width))))
            elif pending & (1 << k):
                self.lane_stalls[k] += 1
                self.tail_lengths[k] = self.tail_lengths[k]+1 if population == 1 else 0

    def observe(self, observation):
        p, item, stage = observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        self.edge_items += int(stage == 'post' and item.edge)
        if stage == 'pre' and p['i_rstb'] == '1':
            if not item.edge:
                self.clockless.add((int('1' in p['o_valid']), int(p['i_valid'])))
            self.ignored_ready.update((k, state) for k, state in enumerate(reversed(p['i_ready']))
                if p['o_valid'][-k-1] == '0' and state in 'xz')
            if p['i_valid'] == '0':
                self.ignored_data.update((bit, state) for bit, state in enumerate(reversed(p['i_data'])) if state in 'xz')

    def report(self):
        c = self.config
        all_mask = c.all_outputs
        masks = set(range(1, all_mask+1)) if c.masked and c.outputs <= 5 else {all_mask}
        populations = range(1, c.outputs+1) if c.masked else (c.outputs,)
        kinds = ('simultaneous', 'staggered') if c.outputs > 1 else ('simultaneous',)
        expected_orders = {(mask, kind) for mask in masks for kind in kinds
            if mask.bit_count() > 1 or kind == 'simultaneous'}
        ready_bins = {(p, kind) for p in range(1, c.outputs+1) for kind in ('none', 'all', 'some')
            if p > 1 or kind != 'some'}
        goals = dict(
            every_small_nonzero_mask=masks <= self.masks,
            every_destination_population=set(populations) <= {mask.bit_count() for mask in self.masks},
            every_single_destination=(not c.masked or {1 << k for k in range(c.outputs)} <= self.masks),
            every_output_first_and_final=set(range(c.outputs)) <= self.first & self.final,
            destination_population_final_consumer=set(product(populations, range(c.outputs))) <= self.population_final,
            mask_completion_order_cross=expected_orders <= self.mask_orders,
            pending_population_ready_class=ready_bins <= self.pending_ready,
            completion_replacement_cross=set(product(kinds, (False, True))) <= self.completions,
            input_acceptance_completion_cross=set(product((False, True), repeat=2)) <= self.accept_completion,
            long_and_one_cycle_stall_every_output=set(product(range(c.outputs), (1, LONG_STALL))) <= self.stalls,
            independent_long_tail_every_output=set(range(c.outputs)) <= {k for k, length in self.tail_stalls if length >= LONG_STALL},
            producer_backpressure=self.maximum_producer_stall >= LONG_STALL,
            consecutive_replacement_stream=self.maximum_stream >= STREAM_LENGTH,
            long_idle=self.long_idle >= LONG_STALL,
            reset_every_pending_population=set(range(c.outputs+1)) <= self.reset_populations,
            clockless_reset_every_pending_population=set(range(c.outputs+1)) <= self.reset_pulses,
            no_combinational_forward_bypass=set(product((0, 1), repeat=2)) <= self.clockless,
            data_pattern_mask_cross=set(product(masks, ('zero', 'one', 'alternating', 'walking_one', 'walking_zero'))) <= self.pattern_masks,
            every_payload_bit_each_lane=set(product(range(-1, c.outputs), range(c.width), '01xz')) <= self.data_bits,
            ignored_invalid_data=set(product(range(c.width), 'xz')) <= self.ignored_data,
            ignored_completed_ready=set(product(range(c.outputs), 'xz')) <= self.ignored_ready,
            copy_conservation=(len(self.ledger) == c.outputs and all(row['pending'] == 0
                and row['accepted'] == row['consumed']+row['discarded'] for row in self.ledger)),
            randomized_campaign=self.random_transactions == c.random_cycles,
            all_sampling_stages=(self.observations['pre'] == self.observations['post'] == self.observations['held']
                and self.observations['edge'] == self.edge_items and self.edge_items > 0))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            token_ledger=self.ledger, destination_masks=sorted(self.masks),
            first_consumers=sorted(self.first), final_consumers=sorted(self.final),
            population_final_bins=sorted(self.population_final), mask_order_bins=sorted(self.mask_orders),
            pending_ready_bins=sorted(self.pending_ready), completion_bins=sorted(self.completions),
            acceptance_completion_bins=sorted(self.accept_completion), stall_bins=sorted(self.stalls),
            independent_tail_stall_bins=sorted(self.tail_stalls),
            maximum_producer_stall=self.maximum_producer_stall, maximum_replacement_stream=self.maximum_stream,
            maximum_idle=self.long_idle, reset_populations=sorted(self.reset_populations),
            clockless_reset_populations=sorted(self.reset_pulses), clockless_bins=sorted(self.clockless),
            pattern_mask_bins=sorted(self.pattern_masks), data_bit_bins=sorted(self.data_bits),
            ignored_ready_bins=sorted(self.ignored_ready), waveform_transitions=dict(self.transitions))
