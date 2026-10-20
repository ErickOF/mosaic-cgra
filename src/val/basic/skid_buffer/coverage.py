"""Require bypass/capture/release coverage, producer stalls and exact conservation."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from skid_buffer.config import LONG_STALL, STALL_LIMIT, STREAM_LENGTH

START_FULL = dict(idle=0, bypass=0, capture=0, hold=1, release=1)
END_FULL = dict(idle=0, bypass=0, capture=1, hold=1, release=0)
OPERATION_PAIRS = {(a, b) for a in START_FULL for b in START_FULL if END_FULL[a] == START_FULL[b]}


class SkidBufferCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cases, self.pairs, self.stalls, self.producer_stalls = set(), set(), set(), set()
        self.reset_cases, self.reset_pulses, self.clockless = set(), set(), set()
        self.patterns, self.data_bits, self.ignored_bits, self.capture_stalls = set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.edge_items = self.first_accepts = self.maximum_stream = self.long_idle = 0
        self.accepted = self.consumed = self.post_release = 0
        self.ledger = {}
        self.reset_epoch()

    def reset_epoch(self):
        self.previous = None
        self.output_stall = self.input_stall = self.streaming = self.idle = 0
        self.capture_classes = set()
        self.first_pending = True

    def record(self, event, ports):
        occupied, operation = event['occupied'], event['operation']
        valid, ready = int(ports['i_valid']), int(ports['i_ready'])
        self.cases.add((occupied, valid, ready))
        if self.previous is not None:
            self.pairs.add((self.previous, operation))
            self.post_release += int(self.previous == 'release' and operation == 'bypass')
        self.previous = operation
        self.accepted += int(event['push'])
        self.consumed += int(event['pop'])
        if event['push'] and self.first_pending:
            self.first_accepts += 1
            self.first_pending = False
        if operation == 'capture':
            self.capture_classes = pattern_classes(ports['i_data'])
            self.output_stall = 0
        elif operation == 'hold':
            self.output_stall += 1
        elif operation == 'release':
            self.stalls.add((self.output_stall, bool(valid)))
            self.capture_stalls.update((name, self.output_stall) for name in self.capture_classes)
            self.output_stall = 0
        if occupied and valid:
            # Ready stays low on the release edge too: count that producer stall.
            self.input_stall += 1
        elif event['push']:
            self.producer_stalls.add(self.input_stall)
            self.input_stall = 0
        self.streaming = self.streaming+1 if operation == 'bypass' else 0
        self.maximum_stream = max(self.maximum_stream, self.streaming)
        self.idle = self.idle+1 if operation == 'idle' else 0
        self.long_idle = max(self.long_idle, self.idle)
        for phase, word in (('bypassed', event['consumed'] if operation == 'bypass' else None),
                ('captured', ports['i_data'] if event['capture'] else None),
                ('released', event['consumed'] if operation == 'release' else None)):
            if word is not None:
                self.patterns.update((phase, name) for name in pattern_classes(word))
                self.data_bits.update((phase, bit, state) for bit, state in enumerate(reversed(word)))

    def observe(self, observation):
        p, item, stage = observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        self.edge_items += int(stage == 'post' and item.edge)
        if stage == 'pre':
            if p['i_rstb'] == '1' and not item.edge:
                self.clockless.add((item.start_count, int(p['i_valid']), int(p['i_ready'])))
            if p['i_valid'] == '0':
                self.ignored_bits.update((bit, state) for bit, state in enumerate(reversed(p['i_data'])) if state in 'xz')

    def report(self):
        c = self.config
        lengths = set(range(STALL_LIMIT+1)) | {LONG_STALL}
        patterns = {'zero', 'one', 'alternating', 'walking_one', 'walking_zero'}
        phases = ('bypassed', 'captured', 'released')
        goals = dict(
            every_state_valid_ready=set(product((0, 1), repeat=3)) <= self.cases,
            every_feasible_operation_pair=OPERATION_PAIRS <= self.pairs,
            buffered_hold_length_waiting_producer_cross=set(product(lengths, (False, True))) <= self.stalls,
            producer_backpressure_lengths=({0} | {length+1 for length in lengths}) <= self.producer_stalls,
            continuous_bypass_stream=self.maximum_stream >= STREAM_LENGTH,
            consecutive_release_and_bypass=self.post_release > 0,
            long_producer_idle=self.long_idle >= LONG_STALL,
            capture_pattern_stall_cross=set(product(patterns, lengths)) <= self.capture_stalls,
            reset_state_handshake_cross=set(product((0, 1), repeat=3)) <= self.reset_cases,
            between_edge_reset_empty_and_full={0, 1} <= self.reset_pulses,
            first_transaction_after_reset=self.first_accepts > 0,
            clockless_bypass_ready_boundary_cross=set(product((0, 1), repeat=3)) <= self.clockless,
            data_pattern_phase_cross=set(product(phases, patterns)) <= self.patterns,
            every_data_bit_bypassed_captured_released=set(product(phases, range(c.width), '01')) <= self.data_bits,
            every_intentional_four_state_bit=set(product(phases, range(c.width), 'xz')) <= self.data_bits,
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
            accepted=self.accepted, consumed=self.consumed, state_valid_ready_bins=sorted(self.cases), token_ledger=self.ledger,
            operation_pairs=sorted(self.pairs), buffered_hold_waiting_bins=sorted(self.stalls),
            producer_stall_lengths=sorted(self.producer_stalls), maximum_bypass_stream=self.maximum_stream,
            post_release_bypasses=self.post_release, maximum_producer_idle=self.long_idle,
            capture_pattern_stall_bins=sorted(self.capture_stalls), reset_bins=sorted(self.reset_cases),
            reset_pulse_states=sorted(self.reset_pulses), first_acceptances_after_reset=self.first_accepts,
            clockless_bins=sorted(self.clockless), pattern_phase_bins=sorted(self.patterns),
            data_bit_bins=sorted(self.data_bits), ignored_data_bit_bins=sorted(self.ignored_bits),
            waveform_transitions=dict(self.transitions),
            external_checks=dict.fromkeys(('native_sva', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
                'technology_mapping', 'physical_timing', 'physical_power', 'forward_chain_timing', 'power_off_policy'), 'NOT_RUN'))
