"""Require transition, latency, throughput, stall, reset and bit coverage."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from register_slice.config import LONG_STALL, STALL_LIMIT, STREAM_LENGTH

START_FULL = dict(idle=0, fill=0, hold=1, consume=1, replace=1)
END_FULL = dict(idle=0, fill=1, hold=1, consume=0, replace=1)
OPERATION_PAIRS = {(a, b) for a in START_FULL for b in START_FULL if END_FULL[a] == START_FULL[b]}


class RegisterSliceCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cases, self.pairs, self.stalls, self.producer_stalls = set(), set(), set(), set()
        self.reset_cases, self.reset_pulses, self.clockless = set(), set(), set()
        self.patterns, self.data_bits, self.ignored_bits = set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.edge_items = self.first_accepts = self.maximum_stream = self.long_idle = 0
        self.accepted = self.consumed = 0
        self.ledger = {}
        self.reset_epoch()

    def reset_epoch(self):
        self.previous = None
        self.output_stall = self.input_stall = self.streaming = self.idle = 0
        self.first_pending = True

    def record(self, event, ports):
        occupied, operation = event['occupied'], event['operation']
        valid, ready = int(ports['i_valid']), int(ports['i_ready'])
        self.cases.add((occupied, valid, ready))
        if self.previous is not None:
            self.pairs.add((self.previous, operation))
        self.previous = operation
        self.accepted += int(event['push'])
        self.consumed += int(event['pop'])
        if event['push'] and self.first_pending:
            self.first_accepts += 1
            self.first_pending = False
        if occupied and not ready:
            self.output_stall += 1
        else:
            if occupied:
                self.stalls.add((self.output_stall, operation == 'replace'))
            self.output_stall = 0
        if occupied and not ready and valid:
            self.input_stall += 1
        elif event['push']:
            self.producer_stalls.add(self.input_stall)
            self.input_stall = 0
        self.streaming = self.streaming+1 if operation == 'replace' else 0
        self.maximum_stream = max(self.maximum_stream, self.streaming)
        self.idle = self.idle+1 if operation == 'idle' else 0
        self.long_idle = max(self.long_idle, self.idle)
        for phase, word in (('accepted', ports['i_data'] if event['push'] else None),
                ('consumed', event['consumed'])):
            if word is not None:
                self.patterns.update((operation, phase, name) for name in pattern_classes(word))
                self.data_bits.update((phase, bit, state) for bit, state in enumerate(reversed(word)))

    def observe(self, observation):
        p, item, stage = observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        self.edge_items += int(stage == 'post' and item.edge)
        if stage == 'pre':
            if p['i_rstb'] == '1' and not item.edge:
                self.clockless.add((int(p['o_valid']), int(p['i_valid']), int(p['i_ready'])))
            if p['i_valid'] == '0':
                self.ignored_bits.update((bit, state) for bit, state in enumerate(reversed(p['i_data'])) if state in 'xz')

    def report(self):
        c = self.config
        lengths = set(range(STALL_LIMIT+1)) | {LONG_STALL}
        patterns = {'zero', 'one', 'alternating', 'walking_one', 'walking_zero'}
        operation_phases = {('fill', 'accepted'), ('replace', 'accepted'), ('replace', 'consumed'), ('consume', 'consumed')}
        goals = dict(
            every_state_valid_ready=set(product((0, 1), repeat=3)) <= self.cases,
            every_feasible_operation_pair=OPERATION_PAIRS <= self.pairs,
            stall_length_replacement_cross=set(product(lengths, (False, True))) <= self.stalls,
            producer_backpressure_lengths=lengths <= self.producer_stalls,
            continuous_replacement_stream=self.maximum_stream >= STREAM_LENGTH,
            long_producer_idle=self.long_idle >= LONG_STALL,
            reset_state_handshake_cross=set(product((0, 1), repeat=3)) <= self.reset_cases,
            between_edge_reset_empty_and_full={0, 1} <= self.reset_pulses,
            first_transaction_after_reset=self.first_accepts > 0,
            clockless_forward_boundary_cross=set(product((0, 1), repeat=3)) <= self.clockless,
            data_pattern_operation_cross={(operation, phase, name) for operation, phase in operation_phases for name in patterns} <= self.patterns,
            every_data_bit_stored_and_consumed=set(product(('accepted', 'consumed'), range(c.width), '01')) <= self.data_bits,
            every_intentional_four_state_bit=set(product(('accepted', 'consumed'), range(c.width), 'xz')) <= self.data_bits,
            invalid_payload_unknown_bits=set(product(range(c.width), 'xz')) <= self.ignored_bits,
            accepted_token_conservation=(bool(self.ledger) and self.ledger['pending'] == 0
                and self.ledger['accepted'] == self.ledger['consumed']+self.ledger['discarded']
                and self.accepted == self.ledger['accepted'] and self.consumed == self.ledger['consumed']),
            randomized_campaign=self.random_transactions == c.random_cycles,
            all_sampling_stages=(self.observations['pre'] == self.observations['post'] == self.observations['held']
                and self.observations['edge'] == self.edge_items and self.edge_items > 0))
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            accepted=self.accepted, consumed=self.consumed, state_valid_ready_bins=sorted(self.cases),
            token_ledger=self.ledger,
            operation_pairs=sorted(self.pairs), stall_replacement_bins=sorted(self.stalls),
            producer_stall_lengths=sorted(self.producer_stalls), maximum_replacement_stream=self.maximum_stream,
            maximum_producer_idle=self.long_idle, reset_bins=sorted(self.reset_cases), reset_pulse_states=sorted(self.reset_pulses),
            first_acceptances_after_reset=self.first_accepts, clockless_bins=sorted(self.clockless),
            pattern_operation_bins=sorted(self.patterns), data_bit_bins=sorted(self.data_bits),
            ignored_data_bit_bins=sorted(self.ignored_bits), waveform_transitions=dict(self.transitions),
            external_checks=dict.fromkeys(('native_sva', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
                'technology_mapping', 'physical_timing', 'physical_power', 'ready_chain_timing', 'power_off_policy'), 'NOT_RUN'))
