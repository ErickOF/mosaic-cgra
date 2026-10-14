"""Mandatory reachable occupancy/handshake crosses and workload measurements."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector


class FifoCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.occupancies, self.handshakes, self.interface_cross = set(), set(), set()
        self.wraps, self.resets, self.transitions_seen = set(), set(), set()
        self.unknown_accepted, self.unknown_consumed = set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.accepted = self.consumed = self.discarded = self.random_transactions = 0
        self.input_stall = self.output_stall = self.stream = 0
        self.max_input_stall = self.max_output_stall = self.max_stream = 0
        self.full_replacements = 0
        self.between_edge_resets = 0

    def record(self, event, ports, count_after):
        count, push, pop = event['count'], event['push'], event['pop']
        self.occupancies.update((count, count_after))
        self.handshakes.add((count, push, pop))
        self.interface_cross.add((count, int(ports['i_valid']), int(ports['i_ready'])))
        self.wraps.add((event['read_wrap'], event['write_wrap']))
        self.accepted += push
        self.consumed += pop
        self.full_replacements += int(count == self.config.depth and push and pop)
        self.transitions_seen.add((count, count_after))
        for attribute, condition in (('input_stall', ports['i_valid'] == '1' and not push),
                                     ('output_stall', count > 0 and ports['i_ready'] == '0'),
                                     ('stream', bool(push and pop))):
            value = getattr(self, attribute) + 1 if condition else 0
            setattr(self, attribute, value)
            setattr(self, 'max_' + attribute, max(getattr(self, 'max_' + attribute), value))
        for word, hits in ((ports['i_data'] if push else '', self.unknown_accepted),
                           (event['consumed'] or '', self.unknown_consumed)):
            hits.update((state, bit) for bit, state in enumerate(reversed(word)) if state in 'xz')

    def report(self):
        config, depth = self.config, self.config.depth
        feasible = {(count, push, pop) for count in range(depth + 1) for push, pop in product((0, 1), repeat=2)
                    if not (count == 0 and pop) and not (count == depth and push and not pop)}
        all_unknowns = set(product('xz', range(config.width)))
        goals = dict(
            every_occupancy=self.occupancies == set(range(depth + 1)),
            occupancy_push_pop=feasible <= self.handshakes,
            occupancy_valid_ready=set(product(range(depth + 1), (0, 1), (0, 1))) <= self.interface_cross,
            all_wrap_combinations=set(product((0, 1), repeat=2)) <= self.wraps,
            reset_every_occupancy=self.resets == set(range(depth + 1)),
            reset_pulse_without_clock=self.between_edge_resets >= 2,
            upward_threshold_crossings=all((level - 1, level) in self.transitions_seen for level in (1, config.almost_full, config.almost_empty + 1, depth)),
            downward_threshold_crossings=all((level, level - 1) in self.transitions_seen for level in (1, config.almost_full, config.almost_empty + 1, depth)),
            full_replacement=self.full_replacements >= 16,
            full_rate=self.max_stream >= max(16, 4 * depth),
            long_producer_stall=self.max_input_stall >= 64,
            long_consumer_stall=self.max_output_stall >= 64,
            every_unknown_data_bit_accepted=all_unknowns <= self.unknown_accepted,
            every_unknown_data_bit_returned=all_unknowns <= self.unknown_consumed,
            randomized_campaign=self.random_transactions == config.random_cycles,
            accepted_item_conservation=self.accepted == self.consumed + self.discarded,
            all_sample_stages=all(self.observations[stage] > 0 for stage in ('pre', 'post', 'held')))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=config.parameters, seed=config.seed,
                    random_transactions=self.random_transactions, accepted=self.accepted, consumed=self.consumed,
                    reset_discarded=self.discarded, goals=goals,
                    structural_assertions='PASS' if config.check_internals else 'NOT_RUN',
                    observations=dict(self.observations), waveform_transitions=dict(self.transitions),
                    occupancy_bins=sorted(self.occupancies), handshake_bins=sorted(self.handshakes),
                    interface_bins=sorted(self.interface_cross), wrap_bins=sorted(self.wraps), reset_bins=sorted(self.resets),
                    full_replacements=self.full_replacements, max_simultaneous_run=self.max_stream,
                    max_producer_stall=self.max_input_stall, max_consumer_stall=self.max_output_stall)
