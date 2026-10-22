"""Checked numerical and timing crosses, with explicit profile-specific waivers."""
from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from mac.transaction import CONTROLS


def boundary_values(c):
    return sorted({0, 1, c.operand_mask, 1 << (c.operand - 1), (1 << (c.operand - 1)) - 1})


def accumulator_values(c, *, exhaustive=False):
    if exhaustive and c.operand <= 2 and c.width <= 6:
        return range(1 << c.width)
    return sorted({0, 1, c.result_mask, 1 << (c.width - 1),
                   (1 << (c.width - 1)) - 1, (1 << (c.width - 1)) + 1})


def exhaustive_values(c):
    return range(1 << c.operand) if c.operand <= 3 else ()


def exhaustive_count(c):
    return (len(exhaustive_values(c)) ** 2 * len(accumulator_values(c, exhaustive=True)) *
            2 * (c.saturation + 1))


def sign(value):
    return (value > 0) - (value < 0)


class MacCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.labels = Counter()
        self.observations = Counter()
        self.modes = set()
        self.boundaries = set()
        self.sign_cross = set()
        self.overflow_cross = set()
        self.carry_cross = set()
        self.exact_limits = set()
        self.zero_cross = set()
        self.negative_cross = set()
        self.valid_enable = set()
        self.causes = set()
        self.unknowns = set()
        self.reset_occupancies = set()
        self.stall_cross = set()
        self.status = set()
        self.workloads = set()
        self.stall = 0
        self.random_transactions = self.exhaustive = 0
        self.storage_checks = self.isolation_checks = 0
        self.accounting = {}

    def record(self, event, item):
        c, kind, p = self.config, event['kind'], item.ports
        self.events[kind] += 1
        self.labels[item.get_name()] += 1
        self.random_transactions += item.random
        if p['i_rstb'] == '1' and p['i_valid'] in ('0', '1') and p['i_clock_enable'] in ('0', '1'):
            self.valid_enable.add((int(p['i_valid']), int(p['i_clock_enable'])))
        if kind == 'reset':
            self.reset_occupancies.add(event['occupancy'])
        self.stall = self.stall + 1 if kind == 'stall' else 0
        if self.stall:
            self.stall_cross.add((event['occupancy'], self.stall))
        if kind == 'illegal':
            self.causes.update(event['causes'])
            self.unknowns.update((name, state) for name in CONTROLS
                                 for state in set(p[name]) & {'x', 'z'})
        if kind != 'legal':
            return
        self.exhaustive += item.get_name() == 'exhaustive'
        signed, saturate = event['modes']
        self.modes.add((signed, saturate))
        self.boundaries.add((signed, int(p['i_operand_a'], 2), int(p['i_operand_b'], 2)))
        self.sign_cross.add((sign(event['product']), sign(event['accumulator']),
                             sign(event['final'])))
        direction = -1 if event['total'] < event['low'] else int(event['total'] > event['high'])
        r = event['response']
        if signed:
            self.overflow_cross.add((direction, saturate, int(r['o_saturated'])))
        else:
            self.carry_cross.add((int(r['o_carry']), saturate, int(r['o_saturated'])))
        for side in ('low', 'high'):
            if event['total'] == event[side]:
                assert r['o_overflow'] == r['o_carry'] == r['o_saturated'] == '0'
                self.exact_limits.add((signed, saturate, side))
        if r['o_zero'] == '1':
            self.zero_cross.add('mathematical_zero' if event['total'] == 0 else 'modular_wrap')
        if r['o_negative'] == '1':
            self.negative_cross.add((sign(event['product']), sign(event['accumulator']), saturate))
        self.status.update(name for name in
                           ('o_carry', 'o_overflow', 'o_saturated', 'o_zero', 'o_negative')
                           if r[name] == '1')
        if item.get_name().startswith('workload_'):
            self.workloads.add(item.get_name())

    def report(self):
        c = self.config
        modes = set(product((0, 1), range(c.saturation + 1)))
        directions = (-1, 0, 1) if c.operand > 1 else (0, 1)
        overflow = {(direction, sat, int(bool(direction) and sat))
                    for direction, sat in product(directions, range(c.saturation + 1))}
        carry = {(value, sat, value * sat)
                 for value, sat in product((0, 1), range(c.saturation + 1))}
        required_status = {'o_carry', 'o_overflow', 'o_zero', 'o_negative'}
        if c.saturation:
            required_status.add('o_saturated')
        causes = set(CONTROLS) | ({'unsupported_saturation'} if not c.saturation else set())
        goals = dict(
            all_legal_mode_crosses=modes <= self.modes,
            boundary_multiplicands_by_signedness=set(product(
                (0, 1), boundary_values(c), boundary_values(c))) <= self.boundaries,
            overflow_direction_by_clamp=overflow <= self.overflow_cross,
            unsigned_carry_by_clamp=carry <= self.carry_cross,
            exact_limits_without_false_flags=set(product(
                (0, 1), range(c.saturation + 1), ('low', 'high'))) <= self.exact_limits,
            zero_from_math_and_wrap={'mathematical_zero', 'modular_wrap'} <= self.zero_cross,
            final_status_conditions=required_status <= self.status,
            all_illegal_causes=causes <= self.causes,
            unknown_controls_x_and_z=set(product(CONTROLS, 'xz')) <= self.unknowns,
            ignored_unknowns=self.labels['invalid_unknowns'] >= 2,
            illegal_unknown_operands_isolated=self.labels['illegal_unknown_data'] >= 4,
            exhaustive_small_widths=self.exhaustive == exhaustive_count(c),
            workloads=len(self.workloads) == 8,
            full_rate=self.labels['full_rate'] >= 96,
            alternating_bubbles=self.labels['alternating_bubbles'] >= 16,
            valid_bubble_enable_cross=set(product((0, 1), (0, 1))) <= self.valid_enable,
            configured_random_campaign=self.random_transactions == c.random_cycles,
            actual_pre_nba_edges=self.observations['edge'] > 0,
            complete_windows=(self.observations['pre'] == self.observations['post'] ==
                              self.observations['held']),
            arithmetic_isolation=not c.check_internals or self.isolation_checks > 0,
            pipeline_enables=not c.check_internals or not c.latency or self.storage_checks > 0,
            exact_response_conservation=(bool(self.accounting) and
                self.accounting['accepted'] == self.accounting['emitted'] +
                self.accounting['reset_discarded']))
        waivers = {}
        if c.latency:
            goals.update(reset_every_occupancy=set(range(c.latency + 1)) <= self.reset_occupancies,
                         occupancy_by_stall_duration=set(product(
                             {0, 1, c.latency}, (1, 3, 32))) <= self.stall_cross,
                         clockless_reset=self.labels['clockless_reset'] > 0)
        else:
            goals['combinational_ignores_clock_controls'] = (
                self.labels['ignored_clock_controls'] >= 6)
            waivers['registered_state'] = 'LATENCY=0 has no clock, reset or enable endpoints'
        if c.operand == 1:
            waivers['negative_product_and_negative_overflow'] = (
                'Signed one-bit operands are 0 or -1; their products are 0 or +1')
        if not c.saturation:
            waivers['clamp'] = 'SUPPORT_SATURATION=0 rejects all saturation requests'
        if not exhaustive_count(c):
            waivers['full_enumeration'] = (
                'Widths above three use boundary crosses and seeded random traffic')
        waivers['feedback_recurrence'] = (
            'Standalone stateless MAC has no feedback wrapper or persistent accumulator')
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters,
                    seed=c.seed, random_transactions=self.random_transactions, goals=goals,
                    numerical_contract=c.contract,
                    events=dict(self.events), observations=dict(self.observations),
                    modes=sorted(self.modes), sign_cross=sorted(self.sign_cross),
                    overflow_cross=sorted(self.overflow_cross),
                    carry_cross=sorted(self.carry_cross),
                    exact_limits=sorted(self.exact_limits), zero_cross=sorted(self.zero_cross),
                    negative_cross=sorted(self.negative_cross),
                    status_conditions=sorted(self.status),
                    illegal_causes=sorted(self.causes),
                    reset_occupancies=sorted(self.reset_occupancies),
                    occupancy_by_stall_duration=sorted(self.stall_cross),
                    exhaustive_vectors=self.exhaustive,
                    expected_exhaustive_vectors=exhaustive_count(c),
                    response_accounting=self.accounting, geometry_waivers=waivers,
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    hdl_arithmetic_assertions='PASS' if c.hdl_assertions else 'NOT_RUN')
