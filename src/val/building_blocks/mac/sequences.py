"""Directed boundaries, small-width enumeration, X/Z, stalls and seeded traffic."""
from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from mac.coverage import accumulator_values, boundary_values, exhaustive_values
from mac.transaction import MacItem


class MacSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('mac_sequence')
        self.c = config
        self.rng = random.Random(config.seed)

    async def cycle(self, label, *, a=1, b=1, accumulator=0, signed=0, saturate=0,
                    valid=1, enable=1, rstb=1, edge=True, random=False, **overrides):
        c = self.c
        ports = dict(i_rstb=rstb, i_clock_enable=enable, i_valid=valid,
                     i_operand_a=a & c.operand_mask, i_operand_b=b & c.operand_mask,
                     i_accumulator=accumulator & c.result_mask, i_signed=signed,
                     i_saturate=saturate)
        ports.update(overrides)
        item = MacItem(label, {name: bits(value, c.widths[name]) for name, value in ports.items()},
                       edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self, label='reset', *, edge=True):
        await self.cycle(label, valid=0, enable=0, rstb=0, edge=edge)

    async def drain(self):
        for _ in range(self.c.latency + 2):
            await self.cycle('drain', valid=0)

    async def boundaries(self):
        c = self.c
        for a, b, accumulator, signed, saturate in product(
                boundary_values(c), boundary_values(c), accumulator_values(c),
                (0, 1), range(c.saturation + 1)):
            await self.cycle('boundaries', a=a, b=b, accumulator=accumulator,
                             signed=signed, saturate=saturate)
        for saturate in (0, 1):
            await self.cycle('unsigned_wrap_to_zero', accumulator=c.result_mask,
                             saturate=saturate)
            await self.cycle('positive_overflow', a=1 << (c.operand - 1),
                             b=1 << (c.operand - 1), accumulator=(1 << (c.width - 1)) - 1,
                             signed=1, saturate=saturate)
            if c.operand > 1:
                await self.cycle('negative_overflow', a=-1, accumulator=1 << (c.width - 1),
                                 signed=1, saturate=saturate)
            for signed, accumulator in ((0, 0), (0, c.result_mask),
                                        (1, 1 << (c.width - 1)),
                                        (1, (1 << (c.width - 1)) - 1)):
                for a, b in ((0, c.operand_mask), (c.operand_mask, 0)):
                    await self.cycle('exact_destination_limit', a=a, b=b, signed=signed,
                                     accumulator=accumulator, saturate=saturate)
            for signed in (0, 1):
                await self.cycle('modular_negative', a=0, accumulator=1 << (c.width - 1),
                                 signed=signed, saturate=saturate)
        # The external accumulator is always a required input, unlike a pure dot product.
        for signed in (0, 1):
            await self.cycle('product_only', a=c.operand_mask, b=c.operand_mask, signed=signed)
            for a, b in ((0, 1), (1, 0)):
                await self.cycle('addend_only', a=a, b=b, accumulator=7, signed=signed)

    async def unknowns(self):
        c = self.c
        for state in 'xz':
            for name in ('i_signed', 'i_saturate'):
                # Illegal controls isolate unknown data as well as known operands.
                await self.cycle('unknown_control', **{name: state})
                await self.cycle('illegal_unknown_data', **{name: state,
                    'i_operand_a': state * c.operand, 'i_operand_b': state * c.operand,
                    'i_accumulator': state * c.width})
            await self.cycle('invalid_unknowns', valid=0, **{name: state * c.widths[name]
                for name in
                ('i_operand_a', 'i_operand_b', 'i_accumulator', 'i_signed', 'i_saturate')})
            if not c.saturation:
                await self.cycle('unsupported_saturation_unknown_data', saturate=1,
                                 i_operand_a=state * c.operand, i_operand_b=state * c.operand,
                                 i_accumulator=state * c.width)
            if c.latency:
                await self.cycle('stalled_unknowns', enable=0, valid=state, **{
                    name: state * c.widths[name] for name in
                    ('i_operand_a', 'i_operand_b', 'i_accumulator', 'i_signed', 'i_saturate')})
            else:
                await self.cycle('ignored_clock_controls', rstb=state, enable=state, edge=False)
        if not c.latency:
            for rstb, enable in product((0, 1), (0, 1)):
                await self.cycle('ignored_clock_controls', rstb=rstb, enable=enable, edge=False)

    async def exhaustive(self):
        c = self.c
        for a, b, accumulator, signed, saturate in product(
                exhaustive_values(c), exhaustive_values(c),
                accumulator_values(c, exhaustive=True), (0, 1), range(c.saturation + 1)):
            await self.cycle('exhaustive', a=a, b=b, accumulator=accumulator,
                             signed=signed, saturate=saturate)

    async def pipeline(self):
        c = self.c
        for index in range(96):
            await self.cycle('full_rate', a=index, b=3, signed=index % 2,
                             accumulator=index * 17, saturate=int(c.saturation and index % 3 == 0))
        for index in range(16):
            await self.cycle('alternating_bubbles', a=index, valid=index % 2)
        for valid, enable in product((0, 1), (0, 1)):
            await self.cycle('valid_enable_cross', valid=valid, enable=enable)
        if not c.latency:
            return
        for occupancy in range(c.latency + 1):
            await self.reset()
            for k in range(occupancy):
                await self.cycle('fill_before_reset', a=k + 1)
            await self.reset('reset_at_position')
        for occupancy, duration in product(sorted({0, 1, c.latency}), (1, 3, 32)):
            await self.reset()
            for k in range(occupancy):
                await self.cycle('fill_before_stall', a=k + 1)
            for _ in range(duration):
                await self.cycle('clock_stall', enable=0, a=self.rng.getrandbits(c.operand),
                                 b=self.rng.getrandbits(c.operand),
                                 accumulator=self.rng.getrandbits(c.width))
            await self.drain()
        for _ in range(c.latency):
            await self.cycle('before_clockless_reset')
        await self.cycle('clockless_input_change', edge=False, a=0, accumulator=0)
        await self.reset('clockless_reset', edge=False)
        await self.cycle('clockless_release', edge=False, valid=0, enable=0)
        await self.drain()

    async def workloads(self):
        c = self.c
        for style in ('signed_random', 'unsigned_random', 'zero_heavy', 'small',
                      'full_toggle', 'product_only', 'addend_only', 'saturation'):
            for index in range(32):
                a, b = self.rng.getrandbits(c.operand), self.rng.getrandbits(c.operand)
                accumulator = self.rng.getrandbits(c.width)
                if style == 'zero_heavy' and index % 4:
                    a = 0
                if style == 'small':
                    a, b, accumulator = index % 3 - 1, index % 5 - 2, index % 7 - 3
                if style == 'full_toggle':
                    a = b = c.operand_mask if index % 2 else 0
                    accumulator = c.result_mask if index % 2 else 0
                if style == 'product_only':
                    accumulator = 0
                if style == 'addend_only':
                    a = 0
                if style == 'saturation':
                    accumulator = (1 << (c.width - 1)) - 1
                    a = b = 1
                await self.cycle('workload_' + style, a=a, b=b, accumulator=accumulator,
                                 signed=int(style != 'unsigned_random'),
                                 saturate=int(c.saturation and style == 'saturation'))

    async def randomized(self):
        c = self.c
        for index in range(c.random_cycles):
            await self.cycle(f'random_{index}', a=self.rng.getrandbits(c.operand),
                             b=self.rng.getrandbits(c.operand),
                             accumulator=self.rng.getrandbits(c.width),
                             signed=self.rng.randrange(2), saturate=self.rng.randrange(2),
                             valid=int(self.rng.random() < 0.8),
                             enable=int(self.rng.random() < 0.8),
                             rstb=int(self.rng.randrange(150) != 0), random=True)

    async def body(self):
        await self.reset()
        await self.reset()
        if self.c.probe:
            name, state = self.c.probe.split(':')
            await self.cycle('protocol_probe', **{name: state * self.c.widths[name]})
            raise AssertionError('Expected protocol assertion did not fire')
        await self.boundaries()
        await self.unknowns()
        await self.exhaustive()
        await self.pipeline()
        await self.workloads()
        await self.randomized()
        await self.drain()
