"""Directed arithmetic/lifecycle boundaries, protection faults and random traffic."""
from random import Random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from polynomial_unit.model import encode, number
from polynomial_unit.images import identity_image
from polynomial_unit.ports import INPUTS
from polynomial_unit.transaction import PolynomialItem


class PolynomialSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('polynomial_sequence')
        self.c = config
        self.rng = Random(config.seed)
        self.bus = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_result_ready=1,
            i_program_response_ready=1)
        self.serial = 0
        self.last = {}

    async def cycle(self, label='cycle', *, edge=True, random=False, fault=None, **ports):
        self.bus.update(ports)
        item = PolynomialItem(f'{self.serial}:{label}', {
            name: bits(value * self.c.widths[name] if isinstance(value, str) else
                       value & ((1 << self.c.widths[name]) - 1) if value < 0 else value,
                       self.c.widths[name]) for name, value in self.bus.items()},
            edge=edge, random=random, fault=fault)
        self.serial += 1
        await self.start_item(item)
        await self.finish_item(item)
        self.last = {name: number(value) for name, value in item.observation.ports.items()}
        return item

    async def drain(self):
        for _ in range(500):
            await self.cycle('drain', i_request_valid=0, i_program_valid=0,
                i_result_ready=1, i_program_response_ready=1, i_flush=0, i_drain=0)
            if self.last['o_idle']:
                return
        raise AssertionError('Polynomial transactions failed to drain')

    def program_fields(self, op, bank=0, index=0, data=0, **metadata):
        c = self.c
        return dict(i_program_command=op, i_program_bank=bank,
            i_program_coefficient_index=index, i_program_coefficient_data=data,
            i_program_degree=0, i_program_x_min=-(1 << (c.INPUT_WIDTH - 1)),
            i_program_x_max=(1 << (c.INPUT_WIDTH - 1)) - 1, i_program_range_policy=0,
            i_program_round_mode=0, i_program_result_shift=0,
            i_program_polynomial_id=(1 << c.POLYNOMIAL_ID_WIDTH) - 1,
            i_program_quality_id=(1 << c.QUALITY_ID_WIDTH) - 1) | {
                'i_program_' + name: value for name, value in metadata.items()}

    async def program(self, op, bank=0, index=0, data=0, **metadata):
        fields = self.program_fields(op, bank, index, data, **metadata)
        for _ in range(500):
            item = await self.cycle('program', i_program_valid=1, **fields)
            if number(item.pre.ports['o_program_ready']):
                await self.cycle('program_release', i_program_valid=0)
                return item
        raise AssertionError('Program request was never accepted')

    def request_fields(self, x, bank=0, predicate=1):
        return dict(i_request_x=x, i_request_bank=bank, i_request_predicate=predicate,
            i_request_context_id=(self.serial * 13) % (1 << self.c.CONTEXT_ID_WIDTH),
            i_request_tag=self.serial % (1 << self.c.REQUEST_TAG_WIDTH))

    async def request(self, x, bank=0, predicate=1):
        fields = self.request_fields(x, bank, predicate)
        for _ in range(500):
            item = await self.cycle('request', i_request_valid=1, **fields)
            if number(item.pre.ports['o_request_ready']):
                await self.cycle('request_release', i_request_valid=0)
                return item
        raise AssertionError('Evaluation request was never accepted')

    async def image(self, degree=0, coefficients=None, bank=0, all_slots=True, **metadata):
        await self.drain()
        await self.program(3, bank)
        coefficients = [3] * (degree + 1) if coefficients is None else coefficients
        for index in range(self.c.MAX_DEGREE + 1 if all_slots else degree + 1):
            await self.program(0, bank, index,
                               coefficients[index] if index < len(coefficients) else 0)
        await self.program(2, bank, degree=degree, **metadata)
        await self.drain()

    async def reset(self):
        await self.cycle('reset', i_rstb=0, i_request_valid=0, i_program_valid=0,
                         i_flush=0, i_drain=0, i_error_clear=0)
        await self.cycle('reset_release', i_rstb=1)

    async def arithmetic(self):
        c = self.c
        for bank in range(c.NUM_BANKS):
            await self.image(c.MAX_DEGREE, bank=bank)
            for index in range(c.MAX_DEGREE + 1):
                await self.program(1, bank, index)
            for x in (-1, 0, 1):
                await self.request(x, bank)
            await self.drain()
        for degree in range(c.MAX_DEGREE + 1):
            await self.image(degree, [(-1 if k % 2 else 1) * (k + 1)
                                     for k in range(degree + 1)])
            for x in (-(1 << (c.INPUT_WIDTH - 1)), -1, 0, 1,
                      (1 << (c.INPUT_WIDTH - 1)) - 1):
                await self.request(x)
            await self.drain()
        for mode in (0, 1):
            for coefficient in (-3, -1, 1, 3):
                await self.image(1, [0, coefficient], round_mode=mode)
                await self.request(1 << (c.FRACTION_WIDTH - 1))
                await self.drain()
            for coefficient in (-3, 3):
                await self.image(0, [coefficient], round_mode=mode, result_shift=1)
                await self.request(0)
                await self.drain()
        maximum = (1 << (c.COEFFICIENT_WIDTH - 1)) - 1
        await self.image(c.MAX_DEGREE, [maximum * (-1 if k % 2 else 1)
                                      for k in range(c.MAX_DEGREE + 1)])
        await self.request(-(1 << (c.INPUT_WIDTH - 1)))
        await self.drain()
        for value in (maximum, -(1 << (c.COEFFICIENT_WIDTH - 1))):
            for shift in (-(c.ACCUMULATOR_WIDTH - 1), 0, c.ACCUMULATOR_WIDTH - 1):
                await self.image(0, [value], result_shift=shift, round_mode=1)
                await self.request(0)
                await self.drain()
        for policy in (0, 1):
            await self.image(1, [1, 1], x_min=-2, x_max=2, range_policy=policy)
            for x in (-3, -2, 0, 2, 3):
                await self.request(x)
            await self.request(3, predicate=0)
            await self.drain()
        identity = identity_image(c.parameters)
        await self.image(1, identity['coefficients'], x_min=identity['x_min'],
            x_max=identity['x_max'], polynomial_id=1, quality_id=0, round_mode=1)
        for x in (identity['x_min'], -1, 0, 1, identity['x_max']):
            await self.request(x)
        await self.drain()
        await self.cycle('arithmetic_done')

    async def timing_and_pressure(self):
        c = self.c
        for degree in range(c.MAX_DEGREE + 1):
            await self.image(degree)
            item = await self.cycle('latency_accept', i_request_valid=1, i_result_ready=0,
                                    **self.request_fields(1))
            assert number(item.pre.ports['o_request_ready']) == 1
            latency = c.MAX_DEGREE + 1 if c.EVALUATION_ARCH else degree + 1
            for distance in range(1, latency + 3):
                await self.cycle(f'latency_{latency}', i_request_valid=0)
                assert self.last['o_result_valid'] == int(distance >= latency), 'Incorrect latency'
            await self.drain()
        await self.image(0)
        accepted = []
        for _ in range(20):
            item = await self.cycle('throughput', i_request_valid=1,
                                    **self.request_fields(1))
            if number(item.pre.ports['o_request_ready']):
                accepted.append(self.serial)
        assert len(accepted) == 20 and all(b - a == 1 for a, b in zip(accepted, accepted[1:]))
        await self.cycle('throughput_done', i_request_valid=0)
        await self.drain()
        await self.image(c.MAX_DEGREE)
        accepted = []
        for _ in range(max(20, 3 * (c.MAX_DEGREE + 1))):
            item = await self.cycle('full_degree_throughput', i_request_valid=1,
                                    **self.request_fields(1))
            if number(item.pre.ports['o_request_ready']):
                accepted.append(self.serial)
        interval = 1 if c.EVALUATION_ARCH else c.MAX_DEGREE + 1
        assert len(accepted) >= 3 and all(b - a == interval for a, b in zip(accepted, accepted[1:]))
        await self.cycle('throughput_done', i_request_valid=0)
        await self.drain()
        await self.image(0)
        for _ in range(c.MAX_DEGREE + c.OUTPUT_QUEUE_DEPTH + 8):
            fields = self.request_fields(0)
            item = await self.cycle('fill_results', i_request_valid=1, i_result_ready=0, **fields)
            if not number(item.pre.ports['o_request_ready']):
                for _ in range(3):
                    await self.cycle('held_request', **fields)
                while True:
                    item = await self.cycle('release_results', i_result_ready=1, **fields)
                    if number(item.pre.ports['o_request_ready']):
                        break
                break
        else:
            raise AssertionError('Result backpressure was never observed')
        await self.cycle('release_request', i_request_valid=0)
        await self.drain()
        for _ in range(c.PROGRAM_RESPONSE_DEPTH):
            await self.cycle('hold_program', i_program_response_ready=0)
            await self.program(1)
        fields = self.program_fields(1)
        for _ in range(3):
            item = await self.cycle('full_program_queue', i_program_valid=1, **fields)
            assert number(item.pre.ports['o_program_ready']) == 0
        await self.cycle('replace_program_head', i_program_response_ready=1)
        await self.cycle('release_program', i_program_valid=0)
        await self.drain()

    async def lifecycle(self):
        c = self.c
        await self.program(3)
        await self.request(0, predicate=0)
        await self.drain()
        if c.NUM_BANKS < 1 << c.widths['i_program_bank']:
            await self.request(0, bank=c.NUM_BANKS)
            await self.program(0, bank=c.NUM_BANKS)
        if c.MAX_DEGREE + 1 < 1 << c.widths['i_program_coefficient_index']:
            await self.program(0, index=c.MAX_DEGREE + 1)
        if c.TRACK_COEFFICIENT_COVERAGE:
            await self.program(2)
        invalid = [dict(x_min=2, x_max=-2), dict(result_shift=-c.ACCUMULATOR_WIDTH)]
        if c.MAX_DEGREE + 1 < 1 << c.widths['i_program_degree']:
            invalid.insert(0, dict(degree=c.MAX_DEGREE + 1))
        for change in invalid:
            await self.program(2, **change)
        await self.image(0, all_slots=False)
        await self.program(0)
        await self.cycle('hold_result', i_result_ready=0)
        await self.request(0)
        await self.program(3)
        await self.drain()
        # Immutable versions survive invalidate and wrap exactly on commit.
        initial = self.last['o_bank_version'] & ((1 << c.BANK_VERSION_WIDTH) - 1)
        for _ in range(1 << c.BANK_VERSION_WIDTH):
            await self.program(3)
            await self.program(0, data=3)
            await self.program(2)
        await self.drain()
        assert self.last['o_bank_version'] & ((1 << c.BANK_VERSION_WIDTH) - 1) == initial
        await self.cycle('version_wrap_done')
        # Lifecycle conflicts win over same-bank evaluation, including rejects.
        item = await self.cycle('same_bank_conflict', i_program_valid=1, i_request_valid=1,
            **self.program_fields(3), **self.request_fields(0))
        assert number(item.pre.ports['o_request_ready']) == 0
        await self.cycle('conflict_release', i_program_valid=0, i_request_valid=0)
        await self.drain()
        if c.NUM_BANKS > 1:
            await self.image(0, bank=0)
            await self.image(0, bank=1)
            item = await self.cycle('different_bank_concurrency', i_program_valid=1,
                i_request_valid=1, **self.program_fields(1, bank=1), **self.request_fields(1))
            assert number(item.pre.ports['o_request_ready']) == 1
            assert number(item.pre.ports['o_program_ready']) == 1
            await self.cycle('concurrent_release', i_program_valid=0, i_request_valid=0)
            await self.drain()

    async def recovery(self):
        c = self.c
        await self.image(c.MAX_DEGREE)
        await self.cycle('hold_program_before_flush', i_program_response_ready=0)
        await self.program(1)
        for position in range(c.MAX_DEGREE + 1):
            await self.cycle('flush_accept', i_request_valid=1, i_result_ready=0,
                             **self.request_fields(1))
            for _ in range(position):
                await self.cycle('advance_to_flush', i_request_valid=0)
            await self.cycle('flush_active', i_flush=1, i_request_valid=0)
            await self.cycle('flush_release', i_flush=0)
        await self.cycle('program_flush_preserved', i_program_response_ready=1)
        await self.drain()
        await self.request(1)
        await self.cycle('drain_requested', i_drain=1)
        for _ in range(c.MAX_DEGREE + 20):
            await self.cycle('drain_wait')
            if self.last['o_drain_done']:
                break
        else:
            raise AssertionError('Drain never completed')
        await self.cycle('drain_release', i_drain=0)
        await self.drain()
        for name in ('i_rstb', 'i_flush', 'i_drain', 'i_error_clear', 'i_request_valid',
                     'i_result_ready', 'i_program_valid', 'i_program_response_ready'):
            for state in ('x', 'z'):
                previous = self.bus[name]
                await self.cycle('unknown_control', **{name: state})
                await self.cycle('known_control', **{name: previous})
        for prefix, fields in (('request', self.request_fields(0)), ('program', self.program_fields(0))):
            for field in fields:
                previous = self.bus[field]
                item = await self.cycle('unknown_field', **(fields | {
                    'i_' + prefix + '_valid': 1, field: 'x'}))
                assert number(item.pre.ports['o_' + prefix + '_ready']) == 0
                await self.cycle('field_release', **{'i_' + prefix + '_valid': 0, field: previous})
        await self.cycle('clear_error', i_error_clear=1)
        await self.cycle('clear_release', i_error_clear=0)
        await self.cycle('clockless_assert', edge=False, i_rstb=0)
        await self.cycle('clockless_release', edge=False, i_rstb=1)
        await self.reset()

    async def protection(self):
        c = self.c
        if c.COEFFICIENT_PROTECTION:
            _, width = encode(3, c.COEFFICIENT_WIDTH, c.COEFFICIENT_PROTECTION)
            for bit in range(width):
                await self.image(0)
                fault = ('coefficient', 0, 0, 0, 1 << bit)
                await self.cycle('inject_bit', fault=fault)
                await self.request(0)
                await self.drain()
                await self.program(1)
                await self.drain()
                await self.cycle('restore_bit', fault=fault)
            # Exercise every stored coefficient selection, including the latest
            # unrolled read copy, and double-error containment with no correction.
            for index in range(c.MAX_DEGREE + 1):
                await self.image(c.MAX_DEGREE)
                copy = c.MAX_DEGREE - index if c.EVALUATION_ARCH else 0
                fault = ('coefficient', 0, copy, index, 3 if c.COEFFICIENT_PROTECTION == 2 else 1)
                await self.cycle('inject_word', fault=fault)
                await self.request(0)
                await self.drain()
                assert self.last['o_fatal_error'] == 1
                await self.cycle('fatal_flush', i_flush=1)
                await self.cycle('fatal_flush_release', i_flush=0)
                assert self.last['o_fatal_error'] == 1
                await self.cycle('restore_word', fault=fault)
            await self.image(0)
            await self.cycle('hold_stage', i_result_ready=0)
            await self.cycle('stage_accept', i_request_valid=1, **self.request_fields(0))
            await self.cycle('stage_corruption', i_request_valid=0, fault=('stage',))
            await self.cycle('latch_stage_fatal')
            assert self.last['o_fatal_error'] == 1
            await self.reset()
        await self.image(0)
        await self.cycle('corrupt_ownership', fault=('ownership', 0))
        await self.cycle('latch_ownership_fatal')
        assert self.last['o_fatal_error'] == 1
        await self.reset()

    async def randomized(self):
        c = self.c
        for bank in range(c.NUM_BANKS):
            await self.image(c.MAX_DEGREE, [self.rng.randrange(-30, 31)
                                          for _ in range(c.MAX_DEGREE + 1)], bank=bank)
        request = None
        command = None
        for index in range(c.random_cycles):
            if request is None and self.rng.random() < .8:
                request = self.request_fields(self.rng.randrange(-(1 << (c.INPUT_WIDTH - 1)),
                    1 << (c.INPUT_WIDTH - 1)), self.rng.randrange(c.NUM_BANKS), self.rng.randrange(2))
            if command is None and self.rng.random() < .25:
                command = self.program_fields(self.rng.choice((0, 1)),
                    self.rng.randrange(c.NUM_BANKS), self.rng.randrange(c.MAX_DEGREE + 1))
            flush = index % 173 == 31
            fields = dict(i_request_valid=int(request is not None and not flush),
                i_program_valid=int(command is not None and not flush), i_flush=int(flush),
                i_result_ready=int(self.rng.random() < .65),
                i_program_response_ready=int(self.rng.random() < .6))
            item = await self.cycle('random', random=True, **(request or {}), **(command or {}), **fields)
            if flush or number(item.pre.ports['o_request_ready']) and fields['i_request_valid']:
                request = None
            if number(item.pre.ports['o_program_ready']) and fields['i_program_valid']:
                command = None
        await self.cycle('random_release', i_flush=0, i_request_valid=0, i_program_valid=0)
        await self.drain()

    async def body(self):
        await self.reset()
        await self.arithmetic()
        await self.timing_and_pressure()
        await self.lifecycle()
        await self.recovery()
        await self.protection()
        await self.randomized()
        await self.drain()
