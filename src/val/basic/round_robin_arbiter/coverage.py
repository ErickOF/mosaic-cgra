"""Mandatory cyclic-order, ownership, error, population and fairness coverage."""
from collections import Counter
from itertools import combinations, product
from mosaic_uvm.components import CoverageCollector
from round_robin_arbiter.config import LOCK_LENGTHS, LONG_STALL, STALL_LIMIT
from round_robin_arbiter.model import known


class ArbiterCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.pointers, self.winners, self.single_cross, self.request_pairs = set(), set(), set(), set()
        self.populations, self.winner_pairs, self.pending_lengths, self.pending_changes = set(), set(), set(), set()
        self.lock_lengths, self.lock_gaps, self.post_lock, self.errors, self.clears, self.pulses = set(), set(), set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.accepted = self.payload_accepts = self.wraps = self.max_stream = 0
        self.maximum_fairness = 0
        self.previous_inputs = None
        self.boundary()

    def boundary(self):
        self.previous_winner = None
        self.pending_length = self.stream = self.lock_beats = 0
        self.last_owner = None
        self.await_post_owner = None

    def record(self, event, ports, model):
        c, winner = self.config, event['winner']
        self.errors.update(event['errors'])
        self.stream = self.stream+1 if event['accepted'] else 0
        self.max_stream = max(self.max_stream, self.stream)
        self.maximum_fairness = max(self.maximum_fairness, *model.waits)
        if isinstance(winner, int) and not event['accepted'] and not event['errors']:
            self.pending_length += 1
        if event['accepted']:
            self.accepted += 1
            self.payload_accepts += int(c.fixture)
            self.winners.add(winner)
            self.pending_lengths.add(self.pending_length)
            self.pending_length = 0
            self.wraps += int(winner == c.requesters-1 and model.order[0] == 0)
            if self.previous_winner is not None: self.winner_pairs.add((self.previous_winner, winner))
            self.previous_winner = winner
            if self.await_post_owner is not None:
                self.post_lock.add((self.await_post_owner, winner))
                self.await_post_owner = None
            if c.has_lock:
                if event['lock']:
                    if event['owner'] is None: self.lock_beats = 0
                    self.lock_beats += 1
                    self.last_owner = winner
                elif event['owner'] is not None:
                    self.lock_lengths.add((winner, self.lock_beats))
                    self.await_post_owner = winner
                    self.lock_beats = 0
        elif event['owner'] is not None and not event['pending'] and not event['errors']:
            if ports['i_request'][-event['owner']-1] == '0': self.lock_gaps.add(event['owner'])
        if event['errors']:
            self.pending_length = 0

    def observe(self, observation):
        c, p, stage = self.config, observation.ports, observation.stage
        self.observations[stage] += 1
        if stage != 'pre' or p['i_rstb'] != '1' or p['i_flush'] != '0': return
        if all(known(p[name]) for name in ('i_request', 'i_eligible', 'o_contended')):
            request, eligible = int(p['i_request'], 2), int(p['i_eligible'], 2)
            self.populations.add((request.bit_count(), eligible.bit_count(), int(p['o_contended'])))
            if request.bit_count() == 2 and eligible == (1 << c.requesters)-1:
                self.request_pairs.add(tuple(r for r in range(c.requesters) if request & (1 << r)))
            if p['o_grant_valid'] == '1' and not int(p['o_pending']) and not int(p['o_locked']) and not int(p['o_protocol_error']):
                pointer = observation.item.pointer_before
                self.pointers.add(pointer)
                if request.bit_count() == 1 and eligible == (1 << c.requesters)-1:
                    self.single_cross.add((pointer, int(p['o_grant_index'], 2)))
            if p['o_pending'] == '1' and p['o_grant_valid'] == '1' and self.previous_inputs:
                winner = int(p['o_grant_index'], 2)
                changes = request ^ self.previous_inputs[0]
                if changes & ~ (1 << winner): self.pending_changes.add(winner)
            self.previous_inputs = request, eligible

    def report(self):
        c, n = self.config, self.config.requesters
        expected_populations = {(r, e, contention) for r, e in product(range(n+1), repeat=2)
            for contention in (0, 1) if (max(0, r+e-n) <= 1 if contention == 0 else min(r, e) >= 2)}
        state_classes = {'idle', 'pending', 'error'} | ({'locked', 'locked_pending'} if c.has_lock else set())
        error_classes = {'invalid_accept', 'pending_request', 'pending_eligibility'} | (
            {'pending_lock', 'owner_eligibility', 'owner_gap_release'} if c.has_lock else {'lock_disabled'})
        goals = dict(
            every_requester_accepted=self.winners == set(range(n)),
            every_pointer_value=self.pointers == set(range(n)),
            pointer_single_request_cross=set(product(range(n), repeat=2)) <= self.single_cross,
            every_request_pair=set(combinations(range(n), 2)) <= self.request_pairs,
            request_eligibility_contention_cross=expected_populations <= self.populations,
            every_accepted_winner_transition=set(product(range(n), repeat=2)) <= self.winner_pairs,
            pointer_wraparound=self.wraps > 0,
            every_pending_length=(set(range(STALL_LIMIT+1)) | {LONG_STALL}) <= self.pending_lengths,
            pending_unselected_request_changes=(self.pending_changes == set(range(n)) if n > 1 else True),
            continuous_acceptance_stream=self.max_stream >= max(16, 2*n),
            every_lock_owner_length=(set(product(range(n), LOCK_LENGTHS)) <= self.lock_lengths if c.has_lock else not self.lock_lengths),
            every_lock_owner_gap=(self.lock_gaps == set(range(n)) if c.has_lock else not self.lock_gaps),
            every_post_lock_winner=(set(product(range(n), repeat=2)) <= self.post_lock if c.has_lock else not self.post_lock),
            every_hardware_error_class=error_classes <= self.errors,
            reset_flush_state_cross=set(product(('reset', 'flush'), state_classes)) <= self.clears,
            between_edge_reset_flush={('reset', 'pending'), ('flush', 'pending')} <= self.pulses,
            randomized_campaign=self.random_transactions == c.random_cycles,
            payload_alignment=(self.payload_accepts > 0 if c.fixture else True),
            all_sampling_stages=self.observations['pre'] == self.observations['post'] == self.observations['held'] and self.observations['edge'] > 0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, payload_fixture=c.fixture,
            seed=c.seed, random_transactions=self.random_transactions, goals=goals, observations=dict(self.observations),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            accepted=self.accepted, payload_acceptances=self.payload_accepts, maximum_fairness_wait=self.maximum_fairness,
            maximum_acceptance_stream=self.max_stream, pointer_wraps=self.wraps, pointer_single_bins=sorted(self.single_cross),
            population_bins=sorted(self.populations), winner_transition_bins=sorted(self.winner_pairs),
            pending_lengths=sorted(self.pending_lengths), pending_change_winners=sorted(self.pending_changes),
            lock_length_bins=sorted(self.lock_lengths), lock_gap_owners=sorted(self.lock_gaps), post_lock_bins=sorted(self.post_lock),
            error_classes=sorted(self.errors), clear_bins=sorted(self.clears), pulse_bins=sorted(self.pulses), waveform_transitions=dict(self.transitions),
            coverage_limits=dict(unselected_change='Unreachable with one requester' if n == 1 else 'applicable',
                locks='Static feature disabled' if not c.has_lock else 'length counts lock-high accepted beats before the final lock-low beat',
                payload='Real mux and register-slice receiver' if c.fixture else 'Separate payload integration profiles'),
            external_checks=dict.fromkeys(('commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp', 'technology_mapping',
                'physical_timing', 'physical_power', 'canonical_requester_ownership', 'lock_cancellation_policy'), 'NOT_RUN'))
