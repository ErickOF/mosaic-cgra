"""Mandatory bins from checked public transactions and mathematical outcomes."""
from collections import Counter
from itertools import product
import hashlib
import json
from mosaic_uvm.components import CoverageCollector


class PolynomialCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.accepted = self.returned = self.discarded = 0
        self.program_accepted = self.program_returned = self.program_discarded = 0
        self.random_cycles = self.flushes = self.unknowns = 0
        self.samples = Counter()
        self.degrees = set()
        self.banks = set()
        self.commands = set()
        self.program_errors = set()
        self.result_errors = set()
        self.ties = set()
        self.saturated_stages = set()
        self.ranges = set()
        self.shifts = set()
        self.predicates = set()
        self.coefficient_reads = set()
        self.readback = set()
        self.output_saturations = set()
        self.fault_bits = set()
        self.hard_faults = set()
        self.labels = set()
        self.latencies = set()
        self.numeric_trace = []
        self.arithmetic_done = False

    def record_evaluation(self, request, result, stats, bank):
        self.banks.add(request['bank'])
        self.result_errors.add(result['error_code'])
        self.predicates.add(result['predicated'])
        self.ties |= stats['ties']
        self.saturated_stages |= stats['saturated_stages']
        if bank:
            self.degrees.add(bank['degree'])
            self.shifts.add((bank['result_shift'] > 0) - (bank['result_shift'] < 0))
            self.ranges.add((bank['range_policy'], result['clipped_low'],
                             result['clipped_high'], result['error_code'] == 11))

    def report(self):
        c = self.config
        maximum = (1 << (c.COEFFICIENT_WIDTH - 1)) - 1
        reachable = set()
        for stage in range(1, c.MAX_DEGREE + 1):
            maximum = maximum * (1 << (c.INPUT_WIDTH - 1)) // (1 << c.FRACTION_WIDTH) + (
                1 << (c.COEFFICIENT_WIDTH - 1))
            if maximum >= 1 << (c.ACCUMULATOR_WIDTH - 1):
                reachable.add(stage)
            maximum = min(maximum, 1 << (c.ACCUMULATOR_WIDTH - 1))
        goals = dict(
            every_degree=set(range(c.MAX_DEGREE + 1)) <= self.degrees,
            every_bank=set(range(c.NUM_BANKS)) <= self.banks,
            every_command=self.commands == set(range(4)),
            coefficient_selection=set(product(range(c.NUM_BANKS), range(c.MAX_DEGREE + 1)))
                <= self.coefficient_reads,
            readback_every_coefficient=set(product(range(c.NUM_BANKS), range(c.MAX_DEGREE + 1)))
                <= self.readback,
            signed_rounding_ties=set(product((0, 1), (0, 1))) <= self.ties,
            reachable_internal_saturation=reachable <= self.saturated_stages,
            output_saturation_both_signs={(1, 0), (1, 1)} <= self.output_saturations,
            all_shift_directions=self.shifts == {-1, 0, 1},
            clip_both_bounds={(0, 1, 0, False), (0, 0, 1, False)} <= self.ranges,
            range_error=(1, 0, 0, True) in self.ranges,
            predicated_response=self.predicates == {0, 1},
            lifecycle_errors={0, 4, 7, 8, 10} <= self.program_errors,
            invalid_degree=(c.MAX_DEGREE + 1 == 1 << c.MAX_DEGREE.bit_length()) or
                6 in self.program_errors,
            incomplete_commit=not c.TRACK_COEFFICIENT_COVERAGE or 9 in self.program_errors,
            illegal_request=3 in self.result_errors,
            numeric_latency=bool(self.latencies),
            arithmetic_trace=bool(self.numeric_trace) and self.arithmetic_done,
            continuous_architecture_throughput='throughput_done' in self.labels,
            held_program_across_flush='program_flush_preserved' in self.labels,
            version_wrap='version_wrap_done' in self.labels,
            clockless_reset='clockless_release' in self.labels,
            unknown_controls=self.unknowns >= 5,
            flush_active=self.flushes >= c.MAX_DEGREE + 1,
            ownership_fault='ownership' in self.hard_faults,
            configured_random_cycles=self.random_cycles == c.random_cycles,
            actual_edge_and_settled_samples=self.samples['edge'] > 1000 and
                self.samples['pre'] == self.samples['post'] == self.samples['held'],
        )
        if c.COEFFICIENT_PROTECTION:
            goals['coefficient_faults'] = bool(self.fault_bits) and 12 in self.result_errors
            goals['protected_live_state'] = 'stage' in self.hard_faults
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
            validation_mode='Python-only', hdl_assertions='NOT_RUN', goals=goals,
            parameters=c.parameters, seed=c.seed, random_transactions=self.random_cycles,
            accepted=self.accepted, returned=self.returned, discarded=self.discarded,
            program_accepted=self.program_accepted, program_returned=self.program_returned,
            program_discarded=self.program_discarded, samples=dict(self.samples),
            degrees=sorted(self.degrees), banks=sorted(self.banks), ties=sorted(self.ties),
            saturated_stages=sorted(self.saturated_stages),
            result_errors=sorted(self.result_errors), program_errors=sorted(self.program_errors),
            coefficient_reads=sorted(self.coefficient_reads), fault_cases=len(self.fault_bits),
            latencies=sorted(self.latencies),
            arithmetic_signature=hashlib.sha256(json.dumps(self.numeric_trace).encode()).hexdigest(),
            external_checks=dict.fromkeys(('lint', 'formal', 'cdc', 'rdc', 'dft', 'low_power',
                'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
