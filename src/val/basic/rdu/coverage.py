"""Coverage from checked accepted advances, tap reads and storage state."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from rdu.config import STALL_LIMIT
from rdu.model import fields, known


class RduCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.delay_valid, self.occupancies, self.drains, self.flushes = set(), set(), set(), set()
        self.stage_states, self.illegal_delays, self.enable_transfer = set(), set(), set()
        self.patterns, self.single_bit_patterns, self.boundaries = set(), set(), set()
        self.priority, self.stall_lengths, self.reset_occupancies, self.ignored_unknowns = set(), set(), set(), set()
        self.observations, self.transitions = Counter(), Counter()
        self.random_transactions = self.reset_pulses = self.stall = self.max_stall = 0
        self.accepted = self.transferred = self.discarded = 0

    def record(self, records, ports, pre):
        config = self.config
        self.enable_transfer.add((ports['i_channel_enable'].count('1'), pre['o_output_transfer'].count('1')))
        if ports['i_advance'] == '0':
            self.stall += 1
            self.max_stall = max(self.max_stall, self.stall)
        else:
            self.stall_lengths.add(self.stall)
            self.stall = 0
        for r in records:
            c, delay = r['channel'], r['delay']
            before = sum(token is not None for token in r['before'])
            after = sum(token is not None for token in r['after'])
            for stage, token in enumerate(r['after']):
                self.stage_states.add((c, stage, int(token is not None)))
            if r['enabled'] and r['legal']:
                self.occupancies.update(((c, delay, before), (c, delay, after)))
                if r['advance'] and not r['flush']:
                    self.delay_valid.add((c, delay, int(r['input_valid'])))
                    if r['input_valid'] == '0':
                        self.drains.add((c, delay, before))
            if r['flush'] and r['legal']:
                self.flushes.add((c, delay, before))
            if r['enabled'] and delay is not None and not r['legal']:
                self.illegal_delays.add((c, delay))
            if r['consumed'] is not None:
                self.patterns.update((c, delay, label) for label in pattern_classes(r['consumed']))
                value = int(r['consumed'], 2)
                maximum = (1 << config.width)-1
                for bit in range(config.width):
                    if value == 1 << bit:
                        self.single_bit_patterns.add((c, delay, bit, 1))
                    if value == maximum ^ (1 << bit):
                        self.single_bit_patterns.add((c, delay, bit, 0))

    def observe(self, observation, model):
        ports = observation.ports
        for name in ('i_delay', 'i_input_valid', 'i_input_data'):
            if not known(ports[name]):
                self.ignored_unknowns.add(name)
        self.accepted, self.transferred, self.discarded = sum(model.accepted), sum(model.transferred), sum(model.discarded)

    def report(self):
        config = self.config
        geometries = {(c, delay) for c, capacity in enumerate(config.capacities) for delay in range(capacity+1)}
        occupancy = {(c, delay, count) for c, delay in geometries for count in range(delay+1)}
        patterns = {'zero', 'one', 'alternating', 'walking_one', 'walking_zero'}
        goals = dict(
            every_delay_and_input_valid={(c, delay, valid) for c, delay in geometries for valid in (0, 1)} <= self.delay_valid,
            every_allocated_stage_validity={(c, stage, valid) for c, capacity in enumerate(config.capacities)
                for stage in range(capacity) for valid in (0, 1)} <= self.stage_states,
            every_delay_occupancy=occupancy <= self.occupancies,
            drain_every_occupancy=occupancy <= self.drains,
            flush_every_occupancy=occupancy <= self.flushes,
            every_illegal_delay={(c, delay) for c, capacity in enumerate(config.capacities)
                for delay in range(capacity+1, 1 << config.delay_width)} <= self.illegal_delays,
            enabled_transfer_populations={(enabled, transferred) for enabled in range(config.channels+1)
                for transferred in range(enabled+1)} <= self.enable_transfer,
            every_stall_length=set(range(STALL_LIMIT+1)) <= self.stall_lengths,
            long_stall=self.max_stall >= 32,
            reset_flush_advance_priority=set(product((0, 1), repeat=3)) <= self.priority,
            empty_and_live_resets={(c, count) for c, capacity in enumerate(config.capacities)
                for count in range(capacity+1)} <= self.reset_occupancies,
            between_edge_reset=self.reset_pulses >= 2,
            legal_reconfiguration={'empty', 'flush', 'reset'} <= self.boundaries if config.total else True,
            data_patterns_at_every_delay={(c, delay, label) for c, delay in geometries for label in patterns} <= self.patterns,
            every_data_bit_at_every_delay={(c, delay, bit, state) for c, delay in geometries
                for bit in range(config.width) for state in (0, 1)} <= self.single_bit_patterns,
            ignored_unknown_inputs={'i_delay', 'i_input_valid', 'i_input_data'} <= self.ignored_unknowns,
            accepted_token_conservation=self.accepted == self.transferred + self.discarded,
            randomized_campaign=self.random_transactions == config.random_cycles,
            all_sampling_stages=self.observations['pre'] == self.observations['post'] == self.observations['held'] and self.observations['pre'] > 0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=config.parameters,
            seed=config.seed, goals=goals, random_transactions=self.random_transactions,
            elaboration_assertions='PASS' if config.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if config.check_internals else 'NOT_RUN',
            capacities=config.capacities, bases=config.bases, observations=dict(self.observations),
            waveform_transitions=dict(self.transitions), delay_valid_bins=sorted(self.delay_valid),
            occupancy_bins=sorted(self.occupancies), drain_bins=sorted(self.drains), flush_bins=sorted(self.flushes),
            stage_validity_bins=sorted(self.stage_states), illegal_delay_bins=sorted(self.illegal_delays),
            enable_transfer_bins=sorted(self.enable_transfer), stall_lengths=sorted(self.stall_lengths),
            longest_stall=self.max_stall, priority_bins=sorted(self.priority), reset_occupancy_bins=sorted(self.reset_occupancies),
            boundary_bins=sorted(self.boundaries), ignored_unknown_bins=sorted(self.ignored_unknowns),
            accepted=self.accepted, transferred=self.transferred, discarded=self.discarded,
            coverage_limits=dict(zero_budget_reconfiguration='Only delay zero is legal; delay-change classes unreachable' if not config.total else 'applicable',
                token_identity='Bit patterns may repeat at small widths; full per-channel token/bubble history and conservation are checked',
                context_integration='NOT_RUN: context identity, mapper artifacts and activation safe points are outside this interface'))
