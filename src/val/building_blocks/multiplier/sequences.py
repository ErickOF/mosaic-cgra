"""Boundary, exhaustive, mixed-mode, power, pipeline and reproducible random traffic."""
from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from multiplier.coverage import boundary_values
from multiplier.transaction import MultiplierItem


class MultiplierSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('multiplier_sequence')
        self.c = config
        self.rng = random.Random(config.seed)

    async def cycle(self, label, *, a=1, b=1, signed_a=0, signed_b=0,
                    valid=1, enable=1, rstb=1, edge=True, random=False, **overrides):
        c = self.c
        ports = dict(i_rstb=rstb, i_clock_enable=enable, i_valid=valid,
                     i_operand_a=a & c.operand_mask, i_operand_b=b & c.operand_mask,
                     i_signed_a=signed_a, i_signed_b=signed_b)
        ports.update(overrides)
        item = MultiplierItem(label, {name: bits(value, c.widths[name])
                                     for name, value in ports.items()}, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self, label='reset', *, edge=True):
        await self.cycle(label, valid=0, enable=0, rstb=0, edge=edge)

    async def drain(self):
        for _ in range(self.c.latency + 2):
            await self.cycle('drain', valid=0)

    async def numerical(self):
        c = self.c
        for a, b, signed_a, signed_b in product(
                boundary_values(c), boundary_values(c), (0, 1), (0, 1)):
            await self.cycle('boundaries', a=a, b=b, signed_a=signed_a, signed_b=signed_b)
        for left, right, signed_a, signed_b in product(
                range(c.operand), range(c.operand), (0, 1), (0, 1)):
            await self.cycle('power_pair', a=1 << left, b=1 << right,
                             signed_a=signed_a, signed_b=signed_b)
        for index, delta, signed_a, signed_b in product(range(c.operand), (-1, 1), (0, 1), (0, 1)):
            a = (1 << index) + delta
            await self.cycle('power_adjacent', a=a, b=c.operand_mask,
                             signed_a=signed_a, signed_b=signed_b)
            await self.cycle('power_adjacent', a=c.operand_mask, b=a,
                             signed_a=signed_a, signed_b=signed_b)
        if c.operand <= 4:
            for a, b, signed_a, signed_b in product(range(1 << c.operand),
                                                   range(1 << c.operand), (0, 1), (0, 1)):
                await self.cycle('exhaustive', a=a, b=b, signed_a=signed_a, signed_b=signed_b)

    async def unknowns(self):
        c = self.c
        for state in 'xz':
            await self.cycle('invalid_unknowns', valid=0, i_operand_a=state * c.operand,
                             i_operand_b=state * c.operand, i_signed_a=state, i_signed_b=state)
            if c.latency:
                await self.cycle('stalled_unknowns', enable=0, valid=state,
                                 i_operand_a=state * c.operand, i_operand_b=state * c.operand,
                                 i_signed_a=state, i_signed_b=state)
            else:
                await self.cycle('ignored_clock_controls', rstb=state, enable=state, edge=False)
        if not c.latency:
            for rstb, enable in product((0, 1), repeat=2):
                await self.cycle('ignored_clock_controls', rstb=rstb, enable=enable, edge=False)
        for index in range(32):
            await self.cycle('changing_invalid', valid=0, a=self.rng.getrandbits(c.operand),
                             b=self.rng.getrandbits(c.operand), signed_a=index % 2,
                             signed_b=(index // 2) % 2)

    async def pipeline(self):
        c = self.c
        modes = tuple(product((0, 1), repeat=2))
        for previous, current in product(modes, repeat=2):
            for _ in range(4):
                await self.cycle('full_rate', a=c.operand_mask, b=1,
                                 signed_a=previous[0], signed_b=previous[1])
            for _ in range(4):
                await self.cycle('full_rate', a=1, b=c.operand_mask,
                                 signed_a=current[0], signed_b=current[1])
        for index in range(16):
            await self.cycle('alternating_bubbles', a=index, valid=index % 2)
        for valid, enable in product((0, 1), repeat=2):
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
                await self.cycle('fill_before_stall', a=k + 1, signed_a=k % 2)
            for _ in range(duration):
                await self.cycle('clock_stall', enable=0, a=self.rng.getrandbits(c.operand),
                                 b=self.rng.getrandbits(c.operand), signed_a=self.rng.randrange(2),
                                 signed_b=self.rng.randrange(2))
            await self.drain()
        # Exercise reset assertion between edges with an occupied pipeline;
        # synchronous profiles retain it until a rising edge samples reset.
        for _ in range(c.latency):
            await self.cycle('before_clockless_reset')
        await self.cycle('clockless_input_change', edge=False, a=0, b=0)
        await self.reset('clockless_reset', edge=False)
        await self.cycle('clockless_release', edge=False, valid=0, enable=0)
        await self.drain()
        await self.reset('clockless_then_clocked_reset', edge=False)
        await self.reset('clocked_reset_after_assertion')
        await self.cycle('immediate_reset_release_traffic', a=c.operand_mask, signed_a=1)
        await self.drain()

    async def workloads(self):
        c = self.c
        for style in ('unsigned', 'signed', 'signed_unsigned', 'unsigned_signed',
                      'zero_heavy', 'small', 'full_toggle', 'one_negative_one'):
            for index in range(32):
                a, b = self.rng.getrandbits(c.operand), self.rng.getrandbits(c.operand)
                signed_a = style != 'unsigned' and style != 'unsigned_signed'
                signed_b = style != 'unsigned' and style != 'signed_unsigned'
                if style == 'zero_heavy' and index % 4:
                    a = 0
                if style == 'small':
                    a, b = index % 3 - 1, index % 5 - 2
                if style == 'full_toggle':
                    a = b = c.operand_mask if index % 2 else 0
                if style == 'one_negative_one':
                    a, b = (1, -1) if index % 2 else (-1, 1)
                await self.cycle('workload_' + style, a=a, b=b,
                                 signed_a=int(signed_a), signed_b=int(signed_b))

    async def randomized(self):
        c = self.c
        for index in range(c.random_cycles):
            await self.cycle(f'random_{index}', a=self.rng.getrandbits(c.operand),
                             b=self.rng.getrandbits(c.operand), signed_a=self.rng.randrange(2),
                             signed_b=self.rng.randrange(2), valid=int(self.rng.random() < 0.8),
                             enable=int(self.rng.random() < 0.8),
                             rstb=int(self.rng.randrange(150) != 0), random=True)

    async def body(self):
        await self.reset()
        await self.reset()
        if self.c.probe:
            name, state = self.c.probe.split(':')
            await self.cycle('protocol_probe', **{name: state * self.c.widths[name]})
            raise AssertionError('Expected protocol assertion did not fire')
        await self.numerical()
        await self.unknowns()
        await self.pipeline()
        await self.workloads()
        await self.randomized()
        await self.drain()
