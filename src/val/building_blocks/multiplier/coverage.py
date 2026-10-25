"""Required numerical/timing crosses and explicit width-specific coverage waivers."""
from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector


def boundary_values(c):
    values = {0, 1, c.operand_mask, 1 << (c.operand - 1), (1 << (c.operand - 1)) - 1}
    if c.operand >= 3:
        values.add(5)
    return sorted(values)


def classes(c, value):
    patterns = dict(zero=0, one=1, negative_one=c.operand_mask,
                    signed_minimum=1 << (c.operand - 1),
                    signed_maximum=(1 << (c.operand - 1)) - 1,
                    unsigned_maximum=c.operand_mask)
    result = {name for name, pattern in patterns.items() if pattern == value}
    if value and value & (value - 1) == 0:
        result.add('power_of_two')
    if not result:
        result.add('interior')
    return result


def exhaustive_count(c):
    return 4 * (1 << (2 * c.operand)) if c.operand <= 4 else 0


def expected_status(c):
    # An unsigned product can set bit 2W-1 only for widths >= 2. The only
    # positive signed one-bit product is (-1)*(-1)=1, whose top product bit is 0.
    values = {(0, 1, 0), (0, 0, 0), (1, 1, 0), (1, 0, 0), (1, 0, 1)}
    if c.operand >= 2:
        values.add((0, 0, 1))
    return values


class MultiplierCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.labels = Counter()
        self.observations = Counter()
        self.modes = set()
        self.boundaries = set()
        self.class_cross = set()
        self.status_cross = set()
        self.mixed_cross = set()
        self.transitions = set()
        self.power_patterns = set()
        self.valid_enable = set()
        self.reset_occupancies = set()
        self.stall_cross = set()
        self.stage_states = set()
        self.frozen_states = set()
        self.workloads = set()
        self.stall = self.run = 0
        self.previous_mode = None
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
        if kind != 'valid':
            if kind in ('reset', 'bubble'):
                self.run = 0
                self.previous_mode = None
            return
        self.exhaustive += item.get_name() == 'exhaustive'
        mode = event['modes']
        self.modes.add(mode)
        if self.previous_mode is not None:
            self.transitions.add((self.previous_mode, mode, min(self.run + 1, 4)))
        self.run += 1
        self.previous_mode = mode
        a, b = int(p['i_operand_a'], 2), int(p['i_operand_b'], 2)
        self.boundaries.add((*mode, a, b))
        self.class_cross.update((*mode, left, right)
                                for left, right in product(classes(c, a), classes(c, b)))
        r = event['response']
        self.status_cross.add((int(r['o_product_signed']), int(r['o_zero']),
                               int(r['o_product'][0])))
        if mode in ((0, 1), (1, 0)):
            self.mixed_cross.add((*mode, (event['product'] > 0) - (event['product'] < 0)))
        if item.get_name() == 'power_pair':
            for value in (a, b):
                if value and value & (value - 1) == 0:
                    self.power_patterns.add(value.bit_length() - 1)
        if item.get_name().startswith('workload_'):
            self.workloads.add(item.get_name())

    def report(self):
        c = self.config
        modes = set(product((0, 1), repeat=2))
        values = boundary_values(c)
        expected_classes = set().union(*(classes(c, value) for value in values))
        class_cross = {(*mode, a, b) for mode, a, b in
                       product(modes, expected_classes, expected_classes)}
        transitions = {(a, b, 4) for a, b in product(modes, repeat=2)}
        goals = dict(
            all_signedness_modes=modes <= self.modes,
            all_boundary_pairs_by_mode={(*m, a, b) for m, a, b in
                product(modes, values, values)} <= self.boundaries,
            operand_classes_by_mode=class_cross <= self.class_cross,
            product_signed_zero_sign_cross=expected_status(c) <= self.status_cross,
            mixed_directions_and_signs={(*m, sign) for m, sign in
                product(((0, 1), (1, 0)), (-1, 0, 1))} <= self.mixed_cross
                if c.operand > 1 else {(*m, sign) for m, sign in
                    product(((0, 1), (1, 0)), (-1, 0))} <= self.mixed_cross,
            full_rate_mode_transitions=transitions <= self.transitions,
            every_power_of_two=set(range(c.operand)) <= self.power_patterns,
            exhaustive_small_widths=self.exhaustive == exhaustive_count(c),
            invalid_unknown_inputs=self.labels['invalid_unknowns'] >= 2,
            changing_invalid_inputs=self.labels['changing_invalid'] >= 32,
            alternating_bubbles=self.labels['alternating_bubbles'] >= 16,
            workloads=len(self.workloads) == 8,
            valid_bubble_enable_cross=set(product((0, 1), repeat=2)) <= self.valid_enable,
            configured_random_campaign=self.random_transactions == c.random_cycles,
            actual_pre_nba_edges=self.observations['edge'] > 0,
            complete_windows=(self.observations['pre'] == self.observations['post'] ==
                              self.observations['held']),
            arithmetic_isolation=not c.check_internals or self.isolation_checks > 0,
            exact_response_conservation=(bool(self.accounting) and
                self.accounting['accepted'] == self.accounting['emitted'] +
                self.accounting['reset_discarded']))
        waivers = {}
        if c.latency:
            states = set(product(range(c.latency), (0, 1)))
            goals.update(reset_every_occupancy=set(range(c.latency + 1)) <= self.reset_occupancies,
                         occupancy_by_stall_duration=set(product(
                             {0, 1, c.latency}, (1, 3, 32))) <= self.stall_cross,
                         all_stage_valid_bubble_states=not c.check_internals or
                             states <= self.stage_states,
                         all_stage_frozen_states=not c.check_internals or
                             states <= self.frozen_states,
                         pipeline_enables=not c.check_internals or self.storage_checks > 0,
                         clockless_reset=self.labels['clockless_reset'] > 0)
        else:
            goals['combinational_ignores_clock_controls'] = (
                self.labels['ignored_clock_controls'] >= 6)
            waivers['registered_state'] = 'LATENCY=0 has no clock, reset or enable endpoints'
        if c.operand == 1:
            waivers['unsigned_product_top_bit'] = 'Unsigned one-bit products are 0 or 1 in two bits'
            waivers['mixed_positive_product'] = 'Signed one-bit operands are 0 or -1'
        if c.operand <= 2:
            waivers['interior_operand_class'] = 'All raw encodings are boundaries or powers of two'
        if not exhaustive_count(c):
            waivers['full_enumeration'] = (
                'Widths above four use boundaries and seeded random traffic')
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters,
                    seed=c.seed, random_transactions=self.random_transactions, goals=goals,
                    numerical_contract=c.contract, events=dict(self.events),
                    observations=dict(self.observations), modes=sorted(self.modes),
                    operand_class_cross=sorted(self.class_cross),
                    product_status_cross=sorted(self.status_cross),
                    mixed_cross=sorted(self.mixed_cross),
                    consecutive_mode_transitions=sorted(self.transitions),
                    reset_occupancies=sorted(self.reset_occupancies),
                    occupancy_by_stall_duration=sorted(self.stall_cross),
                    pipeline_stage_states=sorted(self.stage_states),
                    frozen_stage_states=sorted(self.frozen_states),
                    exhaustive_vectors=self.exhaustive,
                    expected_exhaustive_vectors=exhaustive_count(c),
                    response_accounting=self.accounting, geometry_waivers=waivers,
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    hdl_arithmetic_assertions='PASS' if c.hdl_assertions else 'NOT_RUN')
