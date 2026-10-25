"""Mandatory checked bins, precise profile waivers and reproducible evidence."""
from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from dot_product.transaction import CONTROLS
from dot_product.model import element, interpret


def exhaustive_count(c):
    if c.element * c.terms <= 4:
        return (1 << (2 * c.element * c.terms + c.terms + 1))
    return 0


class DotProductCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.modes = set()
        self.masks = set()
        self.populations = set()
        self.term_states = set()
        self.causes = set()
        self.unknowns = set()
        self.status = set()
        self.boundaries = set()
        self.status_cross = set()
        self.mask_sign_cross = set()
        self.reset_occupancies = set()
        self.stall_occupancies = set()
        self.labels = Counter()
        self.workloads = set()
        self.random_transactions = self.exhaustive = 0
        self.storage_checks = self.isolation_checks = 0
        self.stall = self.maximum_stall = 0
        self.accounting = {}

    def record(self, event, item):
        c, kind = self.config, event['kind']
        self.events[kind] += 1
        self.labels[item.get_name()] += 1
        self.random_transactions += item.random
        if kind == 'reset':
            self.reset_occupancies.add(event['occupancy'])
        if kind == 'stall':
            self.stall += 1
            self.maximum_stall = max(self.maximum_stall, self.stall)
            self.stall_occupancies.add(event['occupancy'])
        else:
            self.stall = 0
        if kind == 'illegal':
            self.causes.update(event['causes'])
            for name in CONTROLS:
                self.unknowns.update((name, state) for state in set(item.ports[name]) & {'x', 'z'})
        if kind != 'legal':
            return
        self.exhaustive += item.get_name() == 'exhaustive'
        self.modes.add(event['modes'])
        signed, accumulate, saturate = event['modes']
        boundary_values = {0, 1, c.word_mask, 1 << (c.element - 1), (1 << (c.element - 1)) - 1}
        for k in range(c.terms):
            if event['mask'] & (1 << k):
                a = int(element(item.ports['i_operand_a'], k, c.element), 2)
                b = int(element(item.ports['i_operand_b'], k, c.element), 2)
                if a in boundary_values and b in boundary_values:
                    value = event['products'][k]
                    self.boundaries.add((signed, a, b, (value > 0) - (value < 0)))
        self.status_cross.add((*event['modes'], *(int(event['response'][name]) for name in
                              ('o_carry', 'o_overflow', 'o_saturated'))))
        population = event['mask'].bit_count()
        shape = 'empty' if not population else 'full' if population == c.terms else 'onehot' if population == 1 else 'partial'
        value = interpret(event['final'], c.width, signed)
        self.mask_sign_cross.add((shape, (value > 0) - (value < 0)))
        self.masks.add(event['mask'])
        self.populations.add(event['mask'].bit_count())
        self.term_states.update((index, bool(event['mask'] & (1 << index))) for index in range(c.terms))
        for name in ('o_carry', 'o_overflow', 'o_saturated', 'o_zero', 'o_negative'):
            if event['response'][name] == '1':
                self.status.add(name)
        if event['total'] < event['low']:
            self.status.add('negative_overflow')
        if event['total'] > event['high'] and event['modes'][0]:
            self.status.add('positive_overflow')
        if event['total'] in (event['low'], event['high']) and event['response']['o_saturated'] == '0':
            self.status.add('exact_limit')
        if any(value < 0 for value in event['products']) and any(value > 0 for value in event['products']):
            self.status.add('mixed_products')
        if item.get_name().startswith('workload_'):
            self.workloads.add(item.get_name())

    def report(self):
        c = self.config
        modes = set(product((0, 1), range(c.accumulate + 1), range(c.saturation + 1)))
        causes = set(CONTROLS)
        if not c.accumulate:
            causes.add('unsupported_accumulate')
        if not c.saturation:
            causes.add('unsupported_saturation')
        required = {'o_zero'}
        if c.element > 1 or c.accumulate:
            required.add('o_negative')
        waivers = {}
        if c.accumulate:
            required |= {'o_carry', 'o_overflow', 'positive_overflow'}
            if c.saturation:
                required.add('o_saturated')
            if c.element > 1:
                required.add('negative_overflow')
        else:
            waivers['carry_overflow_saturation'] = 'Pure products fit ACC_WIDTH; accumulation is compiled out'
        if c.element == 1:
            waivers['negative_product_and_negative_overflow'] = 'Signed one-bit terms are zero or minus one; products are nonnegative'
        if c.element > 1 and c.terms > 1:
            required.add('mixed_products')
        values = {0, 1, c.word_mask, 1 << (c.element - 1), (1 << (c.element - 1)) - 1}
        expected_boundaries = set()
        for signed, a, b in product((0, 1), values, values):
            value = interpret(a, c.element, signed) * interpret(b, c.element, signed)
            expected_boundaries.add((signed, a, b, (value > 0) - (value < 0)))
        expected_status = {(*mode, 0, 0, 0) for mode in modes}
        if c.accumulate:
            expected_status |= {(signed, 1, saturate, int(not signed), signed, saturate)
                                for signed, saturate in product((0, 1), range(c.saturation + 1))}
        goals = dict(operand_boundaries_by_product_sign=expected_boundaries <= self.boundaries,
                     final_carry_overflow_by_saturation=expected_status <= self.status_cross,
                     all_legal_mode_crosses=modes <= self.modes,
                     all_term_masks=self.masks == set(range(c.mask + 1)),
                     all_active_counts=self.populations == set(range(c.terms + 1)),
                     each_term_selected_and_masked=set(product(range(c.terms), (False, True))) <= self.term_states,
                     all_illegal_causes=causes <= self.causes,
                     unknown_controls_x_and_z=set(product(CONTROLS, 'xz')) <= self.unknowns,
                     required_numerical_status=required <= self.status,
                     exact_limits_without_false_saturation='exact_limit' in self.status,
                     ignored_masked_unknowns=self.labels['masked_unknowns'] > 0,
                     ignored_accumulator_unknowns=self.labels['pure_unknown_accumulator'] > 0,
                     changing_invalid_inputs=self.labels['invalid_unknowns'] > 0,
                     exhaustive_small_products=self.exhaustive == exhaustive_count(c),
                     representative_workloads=len(self.workloads) == 4,
                     enabled_full_rate_stream=self.labels['full_rate'] >= 64,
                     configured_random_campaign=self.random_transactions == c.random_cycles,
                     actual_pre_nba_edges=self.observations['edge'] > 0,
                     complete_observation_windows=self.observations['pre'] == self.observations['post'] == self.observations['held'],
                     arithmetic_isolation_checked=not c.check_internals or self.isolation_checks > 0,
                     pipeline_data_enables_checked=not c.check_internals or not c.latency or self.storage_checks > 0,
                     exact_response_conservation=bool(self.accounting) and self.accounting['accepted'] == self.accounting['emitted'] + self.accounting['reset_discarded'])
        if c.latency:
            goals.update(long_stalls=self.maximum_stall >= 32,
                         every_pipeline_reset_position=set(range(c.latency + 1)) <= self.reset_occupancies,
                         empty_and_full_stalls={0, c.latency} <= self.stall_occupancies,
                         clockless_reset_and_input_changes=self.labels['clockless_reset'] > 0)
        else:
            goals['zero_latency_ignores_clock_reset_and_enable'] = self.labels['ignored_clock_controls'] >= 4
            waivers['pipeline_stalls_and_reset_positions'] = 'LATENCY=0 contains no registers; clock, enable and reset are ignored'
        if not exhaustive_count(c):
            waivers['exhaustive_vectors'] = 'Full vector enumeration is restricted to packed operand widths <= 4; larger profiles use boundaries, every mask, workloads and seeded random inputs'
        if not c.saturation:
            waivers['clamp'] = 'SUPPORT_SATURATION=0 rejects saturation requests'
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters,
                    seed=c.seed, random_transactions=self.random_transactions, goals=goals,
                    events=dict(self.events), observations=dict(self.observations),
                    operand_boundary_sign_cross=sorted(self.boundaries),
                    status_cross=sorted(self.status_cross), mask_sign_cross=sorted(self.mask_sign_cross),
                    modes=sorted(self.modes), mask_populations=sorted(self.populations),
                    status_conditions=sorted(self.status), illegal_causes=sorted(self.causes),
                    reset_occupancies=sorted(self.reset_occupancies),
                    stall_occupancies=sorted(self.stall_occupancies), maximum_stall=self.maximum_stall,
                    exhaustive_vectors=self.exhaustive, expected_exhaustive_vectors=exhaustive_count(c),
                    response_accounting=self.accounting, geometry_waivers=waivers,
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    hdl_arithmetic_assertions='PASS' if c.hdl_assertions else 'NOT_RUN')
