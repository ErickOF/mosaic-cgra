"""Boundary, exhaustive, four-state and seeded-random combinational requests."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from scalar_alu.transaction import AluItem, INPUTS


def exhaustive_count(c):
    return 32 * 8 * (1 << (2 * c.width)) if c.width <= 3 else 0


class AluSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('scalar_alu_sequence')
        self.c = config
        self.rng = random.Random(config.seed)

    async def request(
        self,
        label,
        *,
        opcode=0,
        a=0,
        b=0,
        signed=0,
        saturate=0,
        predicate=0,
        enable=1,
        random=False,
        exhaustive=False,
        **overrides,
    ):
        values = dict(zip(INPUTS, (enable, opcode, a, b, predicate, signed, saturate), strict=True))
        values.update(overrides)
        ports = {name: bits(value, self.c.widths[name]) for name, value in values.items()}
        item = AluItem(label, ports, random=random, exhaustive=exhaustive)
        await self.start_item(item)
        await self.finish_item(item)

    async def directed(self):
        c = self.c
        values = sorted({0, 1, c.mask, c.mask - 1, 1 << (c.width - 1), (1 << (c.width - 1)) - 1})
        # All encodings and every control combination, including unsupported modes.
        for op, signed, sat, pred in product(range(32), range(2), range(2), range(2)):
            await self.request(
                'opcode_mode', opcode=op, a=c.mask, b=1, signed=signed, saturate=sat, predicate=pred
            )
        for op in range(20):
            for signed, sat in product(range(2), range(2) if op < 2 else (0,)):
                for a, b in product(values, repeat=2):
                    for pred in range(2) if op == 15 else (0,):
                        await self.request(
                            'boundary',
                            opcode=op,
                            a=a,
                            b=b,
                            signed=signed,
                            saturate=sat,
                            predicate=pred,
                        )
        amounts = {
            value for value in (0, 1, c.width - 1, c.width, c.width + 1, c.mask) if value <= c.mask
        }
        amounts.update(1 << index for index in range(c.width))
        for op, a, b in product((6, 7, 8), values, sorted(amounts)):
            await self.request('shift_boundary', opcode=op, a=a, b=b)
        for index in range(c.width):
            a = 1 << index
            for op in range(2, 6):
                await self.request('walking_bit', opcode=op, a=a, b=c.mask ^ a)
                await self.request('walking_zero', opcode=op, a=c.mask ^ a, b=a)

    async def unknowns(self):
        c = self.c
        for state in 'xz':
            for _ in range(8):
                await self.request(
                    'disabled_unknown',
                    enable=0,
                    **{name: state * c.widths[name] for name in INPUTS if name != 'i_enable'},
                )
                await self.request(
                    'disabled_changing',
                    enable=0,
                    opcode=self.rng.randrange(32),
                    a=self.rng.getrandbits(c.width),
                    b=self.rng.getrandbits(c.width),
                    signed=self.rng.randrange(2),
                    saturate=self.rng.randrange(2),
                )
            await self.request('unknown_enable', i_enable=state)
            for index in range(5):
                opcode = ['0'] * 5
                opcode[index] = state
                await self.request('unknown_opcode', i_opcode=''.join(opcode))
            for op in range(20):
                await self.request('unknown_saturate', opcode=op, i_saturate=state)
                await self.request('unknown_signed', opcode=op, a=c.mask, b=1, i_signed=state)
                await self.request('unknown_predicate', opcode=op, a=c.mask, b=1, i_predicate=state)
            for op in (5, 16):
                await self.request(
                    'ignored_b',
                    opcode=op,
                    a=c.mask,
                    i_operand_b=state * c.width,
                    i_signed=state,
                    i_predicate=state,
                )
            await self.request(
                'ignored_a',
                opcode=17,
                b=c.mask,
                i_operand_a=state * c.width,
                i_signed=state,
                i_predicate=state,
            )
            await self.request(
                'ignored_select_b',
                opcode=15,
                predicate=1,
                a=c.mask,
                i_operand_b=state * c.width,
                i_signed=state,
            )
            await self.request(
                'ignored_select_a',
                opcode=15,
                predicate=0,
                b=c.mask,
                i_operand_a=state * c.width,
                i_signed=state,
            )
            await self.request(
                'illegal_ignores_operands',
                opcode=31,
                i_operand_a=state * c.width,
                i_operand_b=state * c.width,
                i_predicate=state,
                i_signed=state,
            )

    async def exhaustive(self):
        if not exhaustive_count(self.c):
            return
        for op, signed, sat, pred, a, b in product(
            range(32),
            range(2),
            range(2),
            range(2),
            range(1 << self.c.width),
            range(1 << self.c.width),
        ):
            await self.request(
                'exhaustive',
                opcode=op,
                a=a,
                b=b,
                signed=signed,
                saturate=sat,
                predicate=pred,
                exhaustive=True,
            )

    async def body(self):
        if self.c.probe:
            name, state, opcode, predicate = self.c.probe.split(':')
            await self.request(
                'assertion_probe',
                opcode=int(opcode),
                predicate=int(predicate),
                **{name: state * self.c.widths[name]},
            )
            raise AssertionError('Required operand assertion did not fire')
        await self.directed()
        await self.unknowns()
        await self.exhaustive()
        modes = list(product(range(32), range(2), range(2), range(2)))
        self.rng.shuffle(modes)
        for index in range(self.c.random_cycles):
            op, signed, sat, pred = modes[index % len(modes)]
            await self.request(
                'random',
                opcode=op,
                a=self.rng.getrandbits(self.c.width),
                b=self.rng.getrandbits(self.c.width),
                signed=signed,
                saturate=sat,
                predicate=pred,
                random=True,
            )
        await self.request('final_disabled', enable=0)
