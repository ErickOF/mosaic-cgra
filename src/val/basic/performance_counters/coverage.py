"""Coverage from checked state transitions, not sequence names or requested intent."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from performance_counters.model import known


class PerformanceCountersCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.assignments, self.increments, self.gating = set(), set(), set()
        self.arithmetic, self.thresholds, self.snapshot_cross, self.reads = set(), set(), set(), set()
        self.clear_priority, self.config_errors, self.ignored_unknowns, self.boundaries = set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.resets = self.reset_pulses = self.shared_events = 0
        self.snapshot_captures = self.snapshot_replacements = 0

    def record(self, records, ports):
        config = self.config
        for r in records:
            c = r['counter']
            self.gating.add((int(ports['i_global_enable']), int(ports['i_counter_enable'][-c-1]), int(ports['i_freeze'])))
            if r['active'] and r['legal'] and r['valid'] and ports['i_freeze'] == '0':
                self.assignments.add((c, r['selected']))
                self.increments.add(r['amount'])
            if r['clear'] and r['requested']:
                self.clear_priority.add(c)
            if r['requested'] and not r['clear']:
                self.arithmetic.add('overflow' if r['overflow'] else 'no_overflow')
                if r['value'] == config.maximum and not r['overflow']:
                    self.arithmetic.add('exact_maximum')
                if r['old_overflow'] and r['sticky']:
                    self.arithmetic.add('sticky_hold')
            if config.threshold and r['active'] and r['legal']:
                if r['threshold'] is None:
                    self.thresholds.add('disabled')
                else:
                    self.thresholds.add('pulse' if r['pulse'] else 'no_pulse')
                    if r['old'] >= r['threshold'] and r['requested']:
                        self.thresholds.add('already_above')
                    if r['old'] < r['threshold'] and r['value'] < r['threshold']:
                        self.thresholds.add('below')
                    if r['pulse'] and r['overflow'] and not config.saturate:
                        self.thresholds.add('wrap_crossing')
            if r['active'] and not r['legal']:
                self.config_errors.add('selection' if r['selected'] >= config.events else 'threshold_zero')
        selected = [r['selected'] for r in records if r['requested'] and not r['clear']]
        self.shared_events += int(len(selected) > len(set(selected)))
        if config.snapshot:
            capture = int(ports['i_snapshot'])
            self.snapshot_cross.add((capture, int(any(r['requested'] for r in records)), int(any(r['clear'] for r in records))))
            self.snapshot_replacements += int(capture and self.snapshot_captures > 0)
            self.snapshot_captures += capture

    def observe(self, observation, model):
        ports, config = observation.ports, self.config
        for name in ('i_event_select', 'i_event_valid', 'i_event_increment', 'i_read_index', 'i_read_snapshot'):
            if not known(ports[name]):
                self.ignored_unknowns.add(name)
        if ports['i_read_enable'] == '1' and known(ports['i_read_index']):
            source = int(ports['i_read_snapshot'])
            self.reads.add((source, int(ports['o_read_valid']), int(ports['i_read_index'], 2)))

    def report(self):
        config = self.config
        invalid_selection = config.events < 1 << config.event_address_width
        ignored = {'i_event_select', 'i_event_valid', 'i_event_increment', 'i_read_index'}
        if config.snapshot:
            ignored.add('i_read_snapshot')
        goals = dict(
            every_counter_event_assignment=set(product(range(config.counters), range(config.events))) <= self.assignments,
            multiple_counters_one_event=self.shared_events > 0 if config.counters > 1 else True,
            increment_classes={0, 1, config.increment_maximum//2, config.increment_maximum} <= self.increments,
            every_increment_bit={1 << bit for bit in range(config.increment_width)} <= self.increments,
            global_counter_freeze_cross=set(product((0, 1), repeat=3)) <= self.gating,
            every_counter_clear_priority=self.clear_priority == set(range(config.counters)),
            arithmetic_boundaries={'no_overflow', 'overflow', 'exact_maximum', 'sticky_hold'} <= self.arithmetic if config.boundary_feasible else 'no_overflow' in self.arithmetic,
            known_invalid_selection='selection' in self.config_errors if invalid_selection else True,
            threshold_configuration_error='threshold_zero' in self.config_errors if config.threshold else True,
            threshold_crossings={'disabled', 'pulse', 'no_pulse', 'already_above', 'below'} <= self.thresholds if config.threshold else not self.thresholds,
            threshold_crossing_wrap='wrap_crossing' in self.thresholds if config.threshold and not config.saturate and config.increment_width > 1 and config.boundary_feasible else True,
            coherent_snapshot_cross=set(product((0, 1), repeat=3)) <= self.snapshot_cross if config.snapshot else self.snapshot_captures == 0,
            snapshot_replacement=self.snapshot_replacements > 0 if config.snapshot else True,
            every_live_read={(0, 1, c) for c in range(config.counters)} <= self.reads,
            every_snapshot_read={(1, valid, c) for valid, c in product((0, 1), range(config.counters))} <= self.reads if config.snapshot else True,
            ignored_unknowns=ignored <= self.ignored_unknowns,
            cleared_ownership_boundaries={'clear', 'disabled_clear'} <= self.boundaries,
            reset_and_between_edge_pulse=self.resets >= 2 and self.reset_pulses >= 2,
            randomized_campaign=self.random_transactions == config.random_cycles,
            all_sample_stages=self.observations['pre'] == self.observations['post'] == self.observations['held'] and self.observations['pre'] > 0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=config.parameters, seed=config.seed,
            goals=goals, random_transactions=self.random_transactions,
            elaboration_assertions='PASS' if config.check_internals else 'NOT_RUN',
            internal_state_and_isolation='PASS' if config.check_internals else 'NOT_RUN',
            observations=dict(self.observations), waveform_transitions=dict(self.transitions),
            assignment_bins=sorted(self.assignments), increment_values=sorted(self.increments), gating_bins=sorted(self.gating),
            arithmetic_bins=sorted(self.arithmetic), threshold_bins=sorted(self.thresholds),
            snapshot_cross_bins=sorted(self.snapshot_cross), read_bins=sorted(self.reads),
            config_error_bins=sorted(self.config_errors), ignored_unknown_bins=sorted(self.ignored_unknowns),
            boundary_bins=sorted(self.boundaries), snapshot_captures=self.snapshot_captures,
            snapshot_replacements=self.snapshot_replacements, resets=self.resets, reset_pulses=self.reset_pulses,
            coverage_limits=dict(
                arithmetic_boundaries='applicable' if config.boundary_feasible else 'NOT_REACHED: wide counter requires more than 64 maximum increments; reduced-width profiles cover boundaries',
                invalid_selection='unreachable: every representable event ID is legal' if not invalid_selection else 'applicable',
                shared_selection='unreachable with one counter' if config.counters == 1 else 'applicable',
                wrap_crossing='requires threshold, wrapping, multi-bit increments and feasible boundary setup',
                runtime_profiles='NOT_RUN: event producers, architectural IDs and owner tags are outside this primitive'))
