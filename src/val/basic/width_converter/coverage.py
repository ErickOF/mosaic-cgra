"""Mandatory positional, cancellation, throughput and four-state coverage."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from width_converter.config import LONG_STALL, STALL_LIMIT, STREAM_LENGTH


class WidthConverterCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.positions, self.mapping, self.input_populations, self.output_populations = set(), set(), set(), set()
        self.last, self.terminal, self.cancel_states, self.reset_pulses = set(), set(), set(), set()
        self.stalls, self.gaps, self.handshakes, self.packet_lengths = set(), set(), set(), set()
        self.user_values, self.ignored_unknown, self.clockless = set(), set(), set()
        self.input_population_last, self.output_population_last, self.cancel_cross = set(), set(), set()
        self.input_data_bits, self.output_data_bits = set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.edges = self.pushes = self.pops = self.replacements = 0
        self.input_run = self.output_run = self.max_input_run = self.max_output_run = 0
        self.stall = self.gap = self.packet_units = self.long_packet = 0
        self.ledger = {}

    def state(self, model):
        if not model.busy:
            return 'empty'
        if self.config.mode == 'pack' and model.partial:
            return f'partial_{len(model.partial)}'
        if self.config.mode == 'unpack':
            return f'slice_{model.position}'
        return 'complete'

    def cancel(self, item, ports):
        kind = 'reset' if ports['i_rstb'] == '0' else 'flush'
        self.cancel_states.add((kind, item.state_before))
        self.cancel_cross.add((kind, item.state_before, int(ports['i_valid']), int(ports['i_ready'])))
        self.input_run = self.output_run = self.stall = self.gap = self.packet_units = 0

    def record(self, event, ports):
        c = self.config
        push, pop = event['push'], event['pop']
        self.pushes += push
        self.pops += pop
        self.replacements += push and pop
        self.handshakes.add(tuple(int(ports[name]) for name in ('i_valid', 'o_ready', 'o_valid', 'i_ready')))
        self.input_run = self.input_run+1 if push else 0
        self.output_run = self.output_run+1 if pop else 0
        self.max_input_run = max(self.max_input_run, self.input_run)
        self.max_output_run = max(self.max_output_run, self.output_run)
        if ports['o_valid'] == '1' and ports['i_ready'] == '0':
            self.stall += 1
        elif pop:
            self.stalls.add(self.stall)
            self.stall = 0
        if ports['i_valid'] == '0':
            self.gap += 1
        elif push:
            self.gaps.add(self.gap)
            self.gap = 0
        if push:
            beat = event['incoming']
            population = sum(unit is not None for unit in beat.units)
            self.input_populations.add(population)
            self.input_population_last.add((population, int(beat.last)))
            for k, unit in enumerate(beat.units):
                if unit is not None:
                    self.input_data_bits.update((k*c.unit_width+b, state) for b, state in enumerate(reversed(unit)))
            self.user_values.add(beat.user)
            self.packet_units += len(beat.units)
            if beat.last == '1':
                wide = c.wide_units
                self.packet_lengths.add('below' if self.packet_units < wide else 'equal' if self.packet_units == wide else 'above')
                self.long_packet = max(self.long_packet, self.packet_units)
                self.packet_units = 0
            if c.mode == 'pack':
                position = event['position']
                self.positions.add(position)
                self.mapping.add((position, position if c.lsb_first else c.ratio-1-position))
                if event['completion']:
                    self.terminal.add(position)
            elif c.mode == 'unpack':
                self.terminal.add(event['terminal'])
            else:
                self.positions.add(0)
                self.mapping.add((0, 0))
                self.terminal.add(0)
        if pop:
            beat = event['consumed']
            population = sum(unit is not None for unit in beat.units)
            self.output_populations.add(population)
            self.output_population_last.add((population, int(beat.last)))
            for k, unit in enumerate(beat.units):
                if unit is not None:
                    self.output_data_bits.update((k*c.unit_width+b, state) for b, state in enumerate(reversed(unit)))
            self.last.add(beat.last)
            if c.mode == 'unpack':
                self.positions.add(beat.sequence)
                self.mapping.add((beat.sequence, beat.sequence if c.lsb_first else c.ratio-1-beat.sequence))

    def observe(self, observation):
        p, item, stage = observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        self.edges += stage == 'post' and item.edge
        if stage == 'pre':
            if not item.edge and p['i_rstb'] == '1' and p['i_flush'] == '0':
                self.clockless.add((int(p['o_busy']), int(p['o_valid'])))
            for k, bit in enumerate(reversed(p['i_keep'])):
                if bit == '0':
                    end = len(p['i_data'])-k*self.config.unit_width
                    self.ignored_unknown.update(state for state in p['i_data'][end-self.config.unit_width:end] if state in 'xz')

    def report(self):
        c = self.config
        lengths = set(range(STALL_LIMIT+1)) | {LONG_STALL}
        states = {'empty'} | ({f'partial_{k}' for k in range(1, c.ratio)} | {'complete'} if c.mode == 'pack' else
            {f'slice_{k}' for k in range(c.ratio)} if c.mode == 'unpack' else {'complete'})
        handshake_bins = {(v, 1, 0, r) for v, r in product((0, 1), repeat=2)}
        handshake_bins |= {(v, 0, 1, 0) for v in (0, 1)} | {(v, 1, 1, 1) for v in (0, 1)}
        if c.mode == 'unpack':
            handshake_bins |= {(v, 0, 1, 1) for v in (0, 1)}
        goals = dict(
            every_reachable_handshake_cross=handshake_bins <= self.handshakes,
            every_sequence_position=set(range(c.ratio)) <= self.positions,
            every_sequence_physical_mapping={(s, s if c.lsb_first else c.ratio-1-s) for s in range(c.ratio)} <= self.mapping,
            every_input_keep_population=set(range(c.in_units+1)) <= self.input_populations,
            every_output_keep_population=set(range(c.out_units+1)) <= self.output_populations,
            input_keep_population_last_cross=set(product(range(c.in_units+1), (0, 1))) <= self.input_population_last,
            output_keep_population_last_cross=set(product(range(c.out_units+1), (0, 1))) <= self.output_population_last,
            every_data_bit_stored_and_delivered=(set(product(range(c.input_width), '01')) <= self.input_data_bits
                and set(product(range(c.output_width), '01')) <= self.output_data_bits),
            every_terminal_position=set(range(c.ratio)) <= self.terminal,
            terminal_and_nonterminal_outputs={'0', '1'} <= self.last,
            empty_packet_and_invalid_unit_clamping=0 in self.input_populations and 0 in self.output_populations,
            simultaneous_consumption_and_replacement=self.replacements > 0,
            peak_collection_rate=c.mode == 'unpack' or self.max_input_run >= STREAM_LENGTH,
            peak_serialization_rate=c.mode == 'pack' or self.max_output_run >= STREAM_LENGTH,
            short_and_long_output_stalls=lengths <= self.stalls,
            short_and_long_input_gaps=lengths <= self.gaps,
            reset_and_flush_every_retained_state=set(product(('reset', 'flush'), states)) <= self.cancel_states,
            cancellation_state_handshake_cross=set(product(('reset', 'flush'), states, (0, 1), (0, 1))) <= self.cancel_cross,
            between_edge_reset_empty_and_busy={'empty', 'complete' if c.mode != 'unpack' else 'slice_0'} <= self.reset_pulses,
            clockless_forward_boundary={(0, 0), (1, 1)} <= self.clockless,
            ignored_unknown_data={'x', 'z'} <= self.ignored_unknown,
            user_changes_at_group_boundaries=len(self.user_values) >= 2,
            packet_lengths=('above' in self.packet_lengths and 'equal' in self.packet_lengths
                and (c.mode != 'pack' or 'below' in self.packet_lengths)),
            long_packets=self.long_packet >= STREAM_LENGTH*min(c.in_units, c.out_units),
            accepted_unit_and_boundary_conservation=(bool(self.ledger) and not self.ledger['busy']
                and self.ledger['accepted_units'] == self.ledger['consumed_units']+self.ledger['discarded_units']
                and self.ledger['accepted_last'] == self.ledger['consumed_last']+self.ledger['discarded_last']
                and self.pushes == self.ledger['accepted_beats'] and self.pops == self.ledger['consumed_beats']),
            randomized_campaign=self.random_transactions == c.random_cycles,
            actual_edge_and_settled_samples=(self.observations['pre'] == self.observations['post'] == self.observations['held']
                and self.observations['edge'] == self.edges and self.edges > 0))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            mode=c.mode, ratio=c.ratio, token_ledger=self.ledger, input_keep_populations=sorted(self.input_populations),
            output_keep_populations=sorted(self.output_populations), sequence_physical_bins=sorted(self.mapping),
            terminal_bins=sorted(self.terminal), cancellation_bins=sorted(self.cancel_states),
            input_population_last_bins=sorted(self.input_population_last), output_population_last_bins=sorted(self.output_population_last),
            cancellation_handshake_bins=sorted(self.cancel_cross),
            reset_pulse_states=sorted(self.reset_pulses), output_stall_lengths=sorted(self.stalls), input_gap_lengths=sorted(self.gaps),
            maximum_input_run=self.max_input_run, maximum_output_run=self.max_output_run, replacements=self.replacements,
            handshake_bins=sorted(self.handshakes), packet_length_classes=sorted(self.packet_lengths),
            waveform_transitions=dict(self.transitions), external_checks=dict.fromkeys(('hdl_sva', 'commercial_lint', 'cdc',
                'rdc', 'dft', 'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power', 'context_policy'), 'NOT_RUN'))
