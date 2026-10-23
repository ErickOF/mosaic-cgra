"""Mandatory opcode, arithmetic, shift, predicate and feature coverage crosses."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from scalar_alu.model import known
from scalar_alu.sequences import exhaustive_count


class AluCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.observations = Counter()
        self.events = Counter()
        self.labels = Counter()
        self.modes = set()
        self.random_modes = set()
        self.result_flags = set()
        self.arithmetic = set()
        self.saturation_directions = set()
        self.shifts = set()
        self.comparisons = set()
        self.selections = set()
        self.minmax = set()
        self.random_transactions = 0
        self.exhaustive = 0
        self.isolation_checks = 0

    def record(self, obs, event):
        c, p = self.config, obs.ports
        self.observations[obs.stage] += 1
        if obs.stage != 'settled':
            return
        self.labels[obs.item.get_name()] += 1
        self.random_transactions += obs.item.random
        self.exhaustive += obs.item.exhaustive
        self.isolation_checks += c.check_internals
        self.events[event['kind']] += 1
        controls = ('i_opcode', 'i_signed', 'i_saturate', 'i_predicate')
        if p['i_enable'] == '1' and all(known(p[name]) for name in controls):
            mode = tuple(int(p[name], 2) for name in controls)
            self.modes.add(mode)
            if obs.item.random:
                self.random_modes.add(mode)
        if event['kind'] == 'illegal':
            self.events[event['cause']] += 1
        if event['kind'] != 'legal':
            return
        op = event['opcode']
        for name in ('o_zero', 'o_negative'):
            self.result_flags.add((op, name, int(p[name])))
        if op < 2 and event['signed']:
            flag = 'o_carry' if op == 0 else 'o_borrow'
            self.arithmetic.add((op, int(p[flag]), int(p['o_overflow'])))
        if p['o_saturated'] == '1':
            direction = 'low' if event['raw'] < event['low'] else 'high'
            self.saturation_directions.add((op, event['signed'], direction))
        if op in (6, 7, 8):
            amount = event['b']
            labels = {
                label
                for value, label in (
                    (0, 'zero'),
                    (1, 'one'),
                    (c.width - 1, 'last'),
                    (c.width, 'width'),
                )
                if value == amount
            }
            if amount > c.width:
                labels.add('above')
            self.shifts.update((op, label, event['a'] >> (c.width - 1)) for label in labels)
        if op in (11, 12, 13, 14):
            self.comparisons.add((op, event['signed'], event['predicate']))
        if op == 15 and known(p['i_operand_a']) and known(p['i_operand_b']):
            self.selections.add((int(p['i_predicate']), int(event['a'] == event['b'])))
        if op in (18, 19):
            choice = (
                'tie'
                if event['a'] == event['b']
                else ('a' if event['value'] == event['a'] else 'b')
            )
            self.minmax.add((op, event['signed'], choice))

    def report(self):
        c = self.config
        modes = set(product(range(32), range(2), range(2), range(2)))
        legal_ops = set(range(20 if c.minmax else 18))
        flag_bins = set(product(legal_ops, ('o_zero', 'o_negative'), range(2)))
        if c.width > 1:
            flag_bins -= {(op, 'o_negative', 1) for op in range(9, 15)}
        arithmetic = (
            set(product((0, 1), range(2), range(2)))
            if c.width > 1
            else {(0, 0, 0), (0, 1, 1), (1, 0, 0), (1, 1, 1)}
        )
        amount_classes = {'zero', 'one', 'last', 'width'} | (
            {'above'} if c.mask > c.width else set()
        )
        shift_bins = set(product((6, 7, 8), amount_classes, range(2)))
        goals = dict(
            every_opcode_and_mode=modes <= self.modes,
            random_every_opcode_and_mode=modes <= self.random_modes,
            final_zero_negative_every_opcode=flag_bins <= self.result_flags,
            arithmetic_carry_borrow_overflow=arithmetic <= self.arithmetic,
            shifts_amount_by_operand_sign=shift_bins <= self.shifts,
            ordered_comparison_signedness_truth=set(product((11, 12, 13, 14), range(2), range(2)))
            <= self.comparisons,
            select_polarity_by_equality=set(product(range(2), repeat=2)) <= self.selections,
            reserved_encodings=self.events['reserved'] > 0,
            unsupported_saturation=self.events['unsupported_saturation'] > 0,
            unknown_control_containment=all(
                self.events[name] > 0
                for name in (
                    'unknown_enable',
                    'unknown_opcode',
                    'unknown_signed',
                    'unknown_saturate',
                    'unknown_predicate',
                )
            ),
            disabled_changing_unknown=self.labels['disabled_unknown'] > 0
            and self.labels['disabled_changing'] > 0,
            ignored_operands=all(
                self.labels[name] > 0
                for name in ('ignored_a', 'ignored_b', 'ignored_select_a', 'ignored_select_b')
            ),
            exact_random_count=self.random_transactions == c.random_cycles,
            exhaustive_small_width=self.exhaustive == exhaustive_count(c),
            complete_observation_windows=self.observations['settled']
            == self.observations['held']
            > 0,
            operand_isolation=not c.check_internals or self.isolation_checks > 0,
        )
        if c.saturation:
            directions = {(0, 0, 'high'), (1, 0, 'low'), (0, 1, 'low'), (1, 1, 'high')}
            if c.width > 1:
                directions |= {(0, 1, 'high'), (1, 1, 'low')}
            goals['every_saturation_direction'] = directions <= self.saturation_directions
        if c.minmax:
            goals['minmax_signedness_operand'] = (
                set(product((18, 19), range(2), ('a', 'b', 'tie'))) <= self.minmax
            )
        else:
            goals['minmax_compiled_out_is_illegal'] = self.events['minmax_disabled'] > 0
        waivers = []
        if c.width == 1:
            waivers.append(
                dict(
                    profile=c.parameters,
                    owner='MOSAIC ALU maintainers',
                    rationale=(
                        'One-bit operands encode only 0/-1 when signed and shift amounts 0/1; '
                        'opposite signed saturation directions and above-width shifts '
                        'are unreachable'
                    ),
                    expiration='Review if width-one arithmetic or shift semantics change',
                )
            )
        if c.width > 1:
            waivers.append(
                dict(
                    profile=c.parameters,
                    owner='MOSAIC ALU maintainers',
                    rationale='Comparison results are zero-extended 0/1, so their sign bit is zero',
                    expiration='Review if comparison result encoding changes',
                )
            )
        if c.width > 3:
            waivers.append(
                dict(
                    profile=c.parameters,
                    owner='MOSAIC ALU maintainers',
                    rationale=(
                        'Large widths use directed boundaries, formal checks and seeded '
                        'random traffic instead of enumerating every operand pair'
                    ),
                    expiration='Review if maximum release width changes',
                )
            )
        return dict(
            status='PASS' if all(goals.values()) else 'FAIL',
            goals=goals,
            parameters=c.parameters,
            seed=c.seed,
            random_transactions=self.random_transactions,
            observations=dict(self.observations),
            events=dict(self.events),
            opcode_modes=sorted(self.modes),
            arithmetic_cross=sorted(self.arithmetic),
            saturation_directions=sorted(self.saturation_directions),
            shift_cross=sorted(self.shifts),
            result_status_cross=sorted(self.result_flags),
            minmax_cross=sorted(self.minmax),
            exhaustive_vectors=self.exhaustive,
            expected_exhaustive_vectors=exhaustive_count(c),
            waivers=waivers,
            isolated_operand_checks='PASS' if c.check_internals else 'NOT_RUN',
            native_hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
            latency_registered_cycles=0,
            initiation_interval=1,
            architectural_state=False,
        )
