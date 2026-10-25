"""Mandatory numerical, mask, atomicity, reset and clock-enable coverage."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from accumulator.config import LONG_STALL, STREAM_LENGTH
from accumulator.model import Command, calculate, known, lane


def boundary_values(width):
    mask = (1 << width)-1
    sign = 1 << (width-1)
    return sorted({value & mask for value in (0, 1, 2, mask, mask-1, sign, sign-1, sign+1)})


class AccumulatorCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.command_modes, self.populations, self.updated, self.held = set(), set(), set(), set()
        self.valid_classes, self.match_classes, self.transitions_valid, self.transitions_signed = set(), set(), set(), set()
        self.causes, self.invalid_lanes, self.mismatch_lanes, self.mixed_atomic = set(), set(), set(), set()
        self.status_bits, self.overflow_directions, self.clamps, self.boundaries, self.signs = set(), set(), set(), set(), set()
        self.numeric, self.input_bits, self.mask_unknown, self.control_unknown, self.command_unknown = set(), set(), set(), set(), set()
        self.reset_cases, self.reset_pulses, self.stall_bins, self.clockless, self.ignored = set(), set(), set(), set(), set()
        self.unknown_control_cross = set()
        self.legal_masks = set()
        self.random_transactions = self.edges = self.stall = 0
        self.stream_command = None
        self.stream_run = 0
        self.maximum_stream = Counter()
        self.observations, self.transitions = Counter(), Counter()
        self.ledger = {}

    def record(self, event, ports, item):
        c = self.config
        if event['operation'] == 'reset':
            self.reset_cases.add((item.population_before, int(ports['i_clock_enable']), int(ports['i_valid'])))
            self.stall = self.stream_run = 0
            return
        if event['operation'] == 'stall':
            self.stall += 1
            self.stream_run = 0
            return
        if event['accepted'] and known(ports['i_command']):
            self.stall_bins.add((self.stall, int(ports['i_command'], 2)))
        self.stall = 0
        if not event['accepted']:
            self.stream_run = 0
            return
        self.causes.update(event['causes'])
        before, kinds = event['before'], event['kinds']
        for k, bit in enumerate(reversed(ports['i_lane_mask'])):
            if bit in 'xz':
                self.mask_unknown.add((k, bit))
            if bit == '1' and before[k] is None and 'invalid_state' in event['causes']:
                self.invalid_lanes.add(k)
            if bit == '1' and before[k] is not None and known(ports['i_signed']) and kinds[k] != int(ports['i_signed']) and 'signedness_mismatch' in event['causes']:
                self.mismatch_lanes.add(k)
        for k, bit in enumerate(reversed(ports['i_command'])):
            if bit in 'xz':
                self.command_unknown.add((k, bit))
        for name in ('i_signed', 'i_saturate'):
            if ports[name] in 'xz':
                self.control_unknown.add((name, ports[name]))
                if known(ports['i_command']) and known(ports['i_lane_mask']):
                    self.unknown_control_cross.add((name, ports[name], int(ports['i_command'], 2), int(ports['i_lane_mask'], 2) == 0))
        if not all(known(ports[name]) for name in ('i_command', 'i_lane_mask', 'i_signed', 'i_saturate')):
            self.stream_run = 0
            return
        command, signed, saturate = (int(ports[name], 2) for name in ('i_command', 'i_signed', 'i_saturate'))
        requested = {k for k, bit in enumerate(reversed(ports['i_lane_mask'])) if bit == '1'}
        self.command_modes.add((command, signed, saturate))
        self.populations.add((len(requested), command))
        if requested:
            population = sum(before[k] is not None for k in requested)
            classification = 'none' if population == 0 else 'all' if population == len(requested) else 'mixed'
            self.valid_classes.add((command, classification))
            if command >= Command.ADD:
                match = 'invalid' if population != len(requested) else 'match' if all(kinds[k] == signed for k in requested) else 'mismatch'
                self.match_classes.add((command, match))
            if event['causes'] and 0 < population < len(requested):
                self.mixed_atomic.update(event['causes'] & {'invalid_state', 'signedness_mismatch'})
        if event['causes'] and len(requested) > 1 and 'signedness_mismatch' in event['causes']:
            matching = sum(before[k] is not None and kinds[k] == signed for k in requested)
            if 0 < matching < len(requested):
                self.mixed_atomic.add('signedness_mismatch')
        for k in range(c.lanes):
            if k in event['selected']:
                self.updated.add((k, command))
            else:
                self.held.add((k, command))
            if k in requested:
                after_valid = k in event['selected'] or before[k] is not None
                self.transitions_valid.add((command, int(before[k] is not None), int(after_valid)))
                if k in event['selected'] and command in (Command.CLEAR, Command.LOAD):
                    self.transitions_signed.add((command, -1 if kinds[k] is None else kinds[k], signed))
        if before[0] is not None and 0 in requested and known(lane(ports['i_data'], 0, c.width)):
            self.numeric.add((before[0], int(lane(ports['i_data'], 0, c.width), 2), command, signed, saturate))
        if not event['causes']:
            self.legal_masks.add((command, int(ports['i_lane_mask'], 2)))
            self.stream_run = self.stream_run+1 if self.stream_command == command else 1
            self.stream_command = command
            self.maximum_stream[command] = max(self.maximum_stream[command], self.stream_run)
        else:
            self.stream_run = 0
        for k, command, signed, saturate, previous, incoming, result, status, mathematical in event['numeric']:
            for name, bit in status.items():
                self.status_bits.add((name, k, bit))
            if command == Command.LOAD:
                self.input_bits.update((k*c.width+b, bit) for b, bit in enumerate(f'{incoming:0{c.width}b}'[::-1]))
            if command >= Command.ADD:
                low, high = (-(1 << (c.width-1)), (1 << (c.width-1))-1) if signed else (0, c.word_mask)
                if status['overflow']:
                    self.overflow_directions.add('negative' if mathematical < low else 'positive')
                if status['saturated']:
                    self.clamps.add(('signed_' if signed else 'unsigned_') + ('min' if mathematical < low else 'max'))
                if mathematical in (low, high) and not status['saturated']:
                    self.boundaries.add((command, signed, saturate, 'min' if mathematical == low else 'max'))
                self.signs.add((command, signed, saturate, previous >> (c.width-1), incoming >> (c.width-1), result >> (c.width-1)))

    def observe(self, observation):
        p, item, stage = observation.ports, observation.item, observation.stage
        self.observations[stage] += 1
        self.edges += stage == 'post' and item.edge
        if stage == 'pre':
            if not item.edge and p['i_rstb'] == '1':
                self.clockless.add(item.population_before)
            states = set(''.join(p[name] for name in ('i_command', 'i_lane_mask', 'i_data', 'i_signed', 'i_saturate'))) & {'x', 'z'}
            reason = 'stall' if p['i_clock_enable'] == '0' else 'invalid' if p['i_valid'] == '0' else None
            if reason:
                self.ignored.update((reason, state) for state in states)
            if p['i_valid'] == '1' and p['i_command'] == '00':
                self.ignored.update(('clear', state) for state in set(p['i_data']) & {'x', 'z'})

    def report(self):
        c = self.config
        commands = set(range(4 if c.subtract else 3))
        saturation_modes = (0, 1) if c.saturation else (0,)
        arithmetic = (2, 3) if c.subtract else (2,)
        values = boundary_values(c.width)
        feasible_signs = {(op, signed, sat, a >> (c.width-1), b >> (c.width-1), calculate(c.width, op, a, b, signed, sat)[0] >> (c.width-1))
            for op, signed, sat, a, b in product(arithmetic, (0, 1), saturation_modes, values, values)}
        causes = {'unknown_command', 'unknown_mask', 'unknown_signed', 'unknown_saturate', 'nonarithmetic_saturation', 'invalid_state', 'signedness_mismatch'}
        if not c.subtract: causes.add('unsupported_subtract')
        if not c.saturation: causes.add('unsupported_saturation')
        clamps = {'unsigned_max', 'signed_min'}
        if c.subtract: clamps.add('unsigned_min')
        if c.width > 1 or c.subtract: clamps.add('signed_max')
        expected_status = {(name, k, bit) for name in ('carry', 'overflow', 'zero', 'negative') for k, bit in product(range(c.lanes), (0, 1))}
        expected_status |= {(name, k, bit) for name, enabled in (('borrow', c.subtract), ('saturated', c.saturation)) for k, bit in product(range(c.lanes), (0, 1) if enabled else (0,))}
        transitions = {(cmd, old, new) for cmd in range(4) for old, new in ((0, 1), (1, 1)) if cmd < 2}
        transitions |= {(cmd, old, old) for cmd, old in product((2, 3), (0, 1))}
        alternating = sum(1 << k for k in range(c.lanes) if k % 2 == 0)
        mask_shapes = {0, c.all_lanes, alternating, c.all_lanes ^ alternating}
        goals = dict(
            legal_mask_shape_command_cross=set(product(commands, mask_shapes)) <= self.legal_masks,
            command_signedness_saturation_cross=set(product(range(4), (0, 1), (0, 1))) <= self.command_modes,
            mask_population_command_cross=set(product(range(c.lanes+1), range(4))) <= self.populations,
            every_lane_updated_by_implemented_commands=set(product(range(c.lanes), commands)) <= self.updated,
            every_lane_masked_or_illegal_hold=set(product(range(c.lanes), range(4))) <= self.held,
            command_validity_class_cross=set(product(range(4), ('none', 'all') if c.lanes == 1 else ('none', 'all', 'mixed'))) <= self.valid_classes,
            arithmetic_signedness_compatibility_cross=set(product((2, 3), ('match', 'mismatch', 'invalid'))) <= self.match_classes,
            invalid_selected_lane_atomicity=set(range(c.lanes)) <= self.invalid_lanes,
            mismatched_selected_lane_atomicity=set(range(c.lanes)) <= self.mismatch_lanes,
            mixed_legal_illegal_vector_atomicity=c.lanes == 1 or {'invalid_state', 'signedness_mismatch'} <= self.mixed_atomic,
            every_illegal_cause=causes <= self.causes,
            every_status_bit_reachable_value=expected_status <= self.status_bits,
            signed_overflow_directions=({'negative', 'positive'} if c.width > 1 or c.subtract else {'negative'}) <= self.overflow_directions,
            all_supported_saturation_limits=not c.saturation or clamps <= self.clamps,
            exact_boundaries_do_not_saturate=set(product(arithmetic, (0, 1), saturation_modes, ('min', 'max'))) <= self.boundaries,
            arithmetic_sign_cross=feasible_signs <= self.signs,
            validity_transition_command_cross=transitions <= self.transitions_valid,
            initialization_signedness_transition_cross=set(product((0, 1), (-1, 0, 1), (0, 1))) <= self.transitions_signed,
            every_load_data_bit=set(product(range(c.width*c.lanes), '01')) <= self.input_bits,
            reset_population_enable_valid_cross=set(product(range(c.lanes+1), (0, 1), (0, 1))) <= self.reset_cases,
            between_edge_reset_empty_and_full={0, c.lanes} <= self.reset_pulses,
            stalled_command_duration_cross=set(product((*range(5), LONG_STALL), range(4))) <= self.stall_bins,
            full_rate_dependent_commands=all(self.maximum_stream[cmd] >= STREAM_LENGTH for cmd in commands),
            clockless_forward_boundary={0, c.lanes} <= self.clockless,
            ignored_unknown_fields=set(product(('invalid', 'stall', 'clear'), 'xz')) <= self.ignored,
            every_unknown_mask_bit=set(product(range(c.lanes), 'xz')) <= self.mask_unknown,
            every_unknown_command_bit=set(product(range(2), 'xz')) <= self.command_unknown,
            unknown_global_controls=set(product(('i_signed', 'i_saturate'), 'xz')) <= self.control_unknown,
            unknown_controls_command_empty_mask_cross=set(product(('i_signed', 'i_saturate'), 'xz', range(4), (False, True))) <= self.unknown_control_cross,
            small_width_exhaustive=(c.lanes != 1 or c.width > 4 or len(self.numeric) == 16*(1 << (2*c.width))),
            randomized_campaign=self.random_transactions == c.random_cycles,
            command_response_accounting=bool(self.ledger) and self.ledger['accepted'] == self.ledger['legal']+self.ledger['illegal'],
            all_real_sampling_stages=self.observations['pre'] == self.observations['post'] == self.observations['held'] and self.observations['edge'] == self.edges and self.edges > 0)
        waivers = []
        if not c.subtract: waivers.append('SUB cannot update lanes or produce borrow; runtime rejection remains required')
        if not c.saturation: waivers.append('No legal saturation response or clamp; runtime rejection remains required')
        if c.width == 1 and not c.subtract: waivers.append('Signed positive ADD overflow is unreachable at width one')
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, waivers=waivers,
            observations=dict(self.observations), token_ledger=self.ledger,
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            hdl_transition_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
            numerical_cases=len(self.numeric), command_modes=sorted(self.command_modes),
            legal_mask_bins=sorted(self.legal_masks), validity_class_bins=sorted(self.valid_classes), signedness_class_bins=sorted(self.match_classes),
            validity_transition_bins=sorted(self.transitions_valid), signedness_transition_bins=sorted(self.transitions_signed),
            illegal_causes=sorted(self.causes), mixed_atomic_causes=sorted(self.mixed_atomic), status_bins=sorted(self.status_bits),
            overflow_directions=sorted(self.overflow_directions), saturation_limits=sorted(self.clamps),
            boundary_bins=sorted(self.boundaries), maximum_command_streams=dict(self.maximum_stream),
            stall_command_bins=sorted(self.stall_bins), reset_bins=sorted(self.reset_cases),
            waveform_transitions=dict(self.transitions), external_checks=dict.fromkeys(('commercial_lint', 'cdc', 'rdc', 'dft',
                'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power', 'retention', 'tile_context_contract'), 'NOT_RUN'))
