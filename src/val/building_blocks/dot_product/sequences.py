"""Boundary, exhaustive, four-state, pipeline and workload-driven stimulus."""
from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from dot_product.coverage import exhaustive_count
from dot_product.transaction import DotProductItem


class DotProductSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('dot_product_sequence')
        self.c = config
        self.rng = random.Random(config.seed)

    def vector(self, values):
        if isinstance(values, int):
            values = [values] * self.c.terms
        return sum((value & self.c.word_mask) << (k * self.c.element)
                   for k, value in enumerate(values))

    async def cycle(self, label, *, a=1, b=1, mask=None, accumulator=0, signed=0,
                    accumulate=0, saturate=0, valid=1, enable=1, rstb=1,
                    edge=True, random=False, **overrides):
        c = self.c
        ports = dict(i_rstb=rstb, i_clock_enable=enable, i_valid=valid,
                     i_operand_a=self.vector(a), i_operand_b=self.vector(b),
                     i_term_mask=c.mask if mask is None else mask,
                     i_accumulator=accumulator & c.result_mask, i_signed=signed,
                     i_accumulate=accumulate, i_saturate=saturate)
        ports.update(overrides)
        item = DotProductItem(label, {name: bits(value, c.widths[name])
                                     for name, value in ports.items()}, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self, label='reset', **overrides):
        return await self.cycle(label, valid=0, enable=0, rstb=0, **overrides)

    async def drain(self):
        for _ in range(self.c.latency + 2):
            await self.cycle('drain', valid=0)

    async def masks_and_modes(self):
        c = self.c
        for mask in range(c.mask + 1):
            await self.cycle('every_mask', mask=mask, signed=mask % 2,
                             a=[k + 1 for k in range(c.terms)], b=c.word_mask)
        values = sorted({0, 1, c.word_mask, 1 << (c.element - 1), (1 << (c.element - 1)) - 1})
        for k, a, b, signed in product(range(c.terms), values, values, (0, 1)):
            await self.cycle('exact_product', a=a, b=b, mask=1 << k, signed=signed)
        for signed, accumulate, saturate, mask in product((0, 1), (0, 1), (0, 1), (0, c.mask)):
            await self.cycle('mode_cross', signed=signed, accumulate=accumulate,
                             saturate=saturate, mask=mask, accumulator=c.result_mask)
        await self.cycle('reduction_growth', a=c.word_mask, b=c.word_mask)
        if c.element > 1 and c.terms > 1:
            await self.cycle('mixed_sign_reduction', a=[-1 if k % 2 else 1 for k in range(c.terms)],
                             b=1, signed=1)

    async def limits(self):
        c = self.c
        high = (1 << (c.width - 1)) - 1
        low = 1 << (c.width - 1)
        for saturate in (0, 1):
            await self.cycle('unsigned_carry', a=c.word_mask, b=c.word_mask,
                             accumulate=1, accumulator=c.result_mask, saturate=saturate)
            await self.cycle('signed_positive_overflow', a=1 << (c.element - 1),
                             b=1 << (c.element - 1), signed=1, accumulate=1,
                             accumulator=high, saturate=saturate)
            if c.element > 1:
                await self.cycle('signed_negative_overflow', a=-1, b=1, signed=1,
                                 accumulate=1, accumulator=low, saturate=saturate)
                await self.cycle('exact_signed_minimum', a=-1, b=1, mask=1, signed=1,
                                 accumulate=1, accumulator=low + 1, saturate=saturate)
            for signed, accumulator in ((0, c.result_mask), (1, high), (1, low)):
                await self.cycle('empty_accumulator_pass', mask=0, signed=signed,
                                 accumulate=1, accumulator=accumulator, saturate=saturate)
            for signed, accumulator in ((0, c.result_mask - 1), (1, high - 1)):
                await self.cycle('exact_upper_limit', a=1, b=1, mask=1, signed=signed,
                                 accumulate=1, accumulator=accumulator, saturate=saturate)
        for signed, saturate in product((0, 1), (0, 1)):
            await self.cycle('pure_unknown_accumulator', signed=signed, saturate=saturate,
                             i_accumulator='x' * c.width)

    async def unknowns(self):
        c = self.c
        for state in 'xz':
            for name in ('i_signed', 'i_accumulate', 'i_saturate'):
                for mask in (0, c.mask):
                    await self.cycle('unknown_control', mask=mask, **{name: state})
            for k in range(c.terms):
                mask = list(bits(c.mask, c.terms))
                mask[-k - 1] = state
                await self.cycle('unknown_mask', i_term_mask=''.join(mask))
                a = state * (c.element * c.terms)
                end = len(a) - k * c.element
                a = a[:end - c.element] + bits(1, c.element) + a[end:]
                await self.cycle('masked_unknowns', mask=1 << k, i_operand_a=a, i_operand_b=a)
            await self.cycle('masked_unknowns', mask=0,
                             i_operand_a=state * (c.element * c.terms),
                             i_operand_b=state * (c.element * c.terms))
            await self.cycle('invalid_unknowns', valid=0,
                             **{name: state * c.widths[name] for name in
                                ('i_operand_a', 'i_operand_b', 'i_term_mask', 'i_accumulator',
                                 'i_signed', 'i_accumulate', 'i_saturate')})
            if c.latency:
                await self.cycle('stalled_unknowns', enable=0, valid=state,
                                 **{name: state * c.widths[name] for name in
                                    ('i_operand_a', 'i_operand_b', 'i_term_mask', 'i_accumulator',
                                     'i_signed', 'i_accumulate', 'i_saturate')})
            else:
                await self.cycle('ignored_clock_controls', rstb=state, enable=state)
        if not c.latency:
            for rstb, enable in product((0, 1), (0, 1)):
                await self.cycle('ignored_clock_controls', rstb=rstb, enable=enable, edge=False)

    async def exhaustive(self):
        c = self.c
        if not exhaustive_count(c):
            return
        for a, b, mask, signed in product(range(1 << (c.element * c.terms)),
                                          range(1 << (c.element * c.terms)),
                                          range(c.mask + 1), (0, 1)):
            await self.cycle('exhaustive', i_operand_a=a, i_operand_b=b,
                             mask=mask, signed=signed)

    async def pipeline(self):
        c = self.c
        for index in range(96):
            await self.cycle('full_rate', a=[index + k for k in range(c.terms)], b=3,
                             signed=index % 2, accumulate=int(bool(c.accumulate) and index % 3 == 0),
                             accumulator=index, saturate=int(bool(c.saturation) and index % 4 == 0))
        for index in range(16):
            await self.cycle('alternating_bubbles', a=index, b=c.word_mask, valid=index % 2)
        if not c.latency:
            return
        for occupancy in range(c.latency + 1):
            await self.reset()
            for k in range(occupancy):
                await self.cycle('fill_before_reset', a=k + 1, b=1)
            await self.reset('reset_at_position')
        for occupancy, length in product(sorted({0, 1, c.latency}), (1, 3, 32)):
            await self.reset()
            for k in range(occupancy):
                await self.cycle('fill_before_stall', a=k + 1)
            for _ in range(length):
                await self.cycle('clock_stall', enable=0, a=self.rng.randrange(1 << c.element))
            await self.drain()
        await self.cycle('before_clockless_reset')
        await self.cycle('clockless_input_change', edge=False, enable=1, a=0, b=0)
        await self.reset('clockless_reset', edge=False)
        await self.cycle('clockless_release', edge=False, valid=0, enable=0)
        await self.drain()

    async def workloads(self):
        c = self.c
        for name in ('fir', 'convolution', 'matrix', 'attention'):
            for index in range(24):
                if name == 'fir':
                    a = [((index + k) * 5 % 13) - 6 for k in range(c.terms)]
                    b = [1, -2, 3, -1] * ((c.terms + 3) // 4)
                    b = b[:c.terms]
                elif name == 'convolution':
                    a = [((index // 4 + k // 3) * 7 + index % 4 + k % 3) % 11 - 5 for k in range(c.terms)]
                    b = [2 if k % 3 == 1 else -1 for k in range(c.terms)]
                elif name == 'matrix':
                    a = [((index // 4 + 1) * (k + 2)) % 9 - 4 for k in range(c.terms)]
                    b = [((index % 4 + 2) * (k + 1)) % 7 - 3 for k in range(c.terms)]
                else:
                    a = [((index * (k + 1) + 3) % 9) - 4 for k in range(c.terms)]
                    b = [((k * 3 + index) % 7) - 3 for k in range(c.terms)]
                await self.cycle('workload_' + name, a=a, b=b, signed=1,
                                 mask=c.mask ^ (1 << (index % c.terms)) if name == 'attention' else c.mask,
                                 accumulate=c.accumulate, accumulator=(index * 31) & c.result_mask,
                                 saturate=c.saturation)

    async def randomized(self):
        c = self.c
        for index in range(c.random_cycles):
            await self.cycle(f'random_{index}',
                             i_operand_a=self.rng.getrandbits(c.element * c.terms),
                             i_operand_b=self.rng.getrandbits(c.element * c.terms),
                             mask=self.rng.getrandbits(c.terms),
                             accumulator=self.rng.getrandbits(c.width), signed=self.rng.randrange(2),
                             accumulate=self.rng.randrange(2), saturate=self.rng.randrange(2),
                             valid=int(self.rng.random() < 0.8), enable=int(self.rng.random() < 0.8),
                             rstb=int(self.rng.randrange(150) != 0), random=True)

    async def probe(self):
        name, state = self.c.probe.split(':')
        await self.reset()
        await self.cycle('protocol_probe', accumulate=int(name == 'i_accumulator'),
                         **{name: state * self.c.widths[name]})
        raise AssertionError('Expected protocol assertion did not fire')

    async def body(self):
        await self.reset()
        await self.reset()
        if self.c.probe:
            await self.probe()
            return
        await self.masks_and_modes()
        await self.limits()
        await self.unknowns()
        await self.exhaustive()
        await self.pipeline()
        await self.workloads()
        await self.randomized()
        await self.drain()
