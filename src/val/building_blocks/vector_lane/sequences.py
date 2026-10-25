"""Directed, exhaustive, mixed-path and reproducible randomized lane traffic."""

import random
from itertools import product

from mosaic_uvm.logic import bits
from pyuvm import uvm_sequence

from vector_lane.transaction import LaneItem


class LaneSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("vector_lane_sequence")
        self.c = config
        self.rng = random.Random(config.seed)

    async def cycle(
        self,
        label,
        *,
        op=0,
        a=1,
        b=1,
        accumulator=0,
        signed=0,
        saturate=0,
        valid=1,
        lane=1,
        pred_enable=0,
        execute=1,
        select=0,
        enable=1,
        rstb=1,
        edge=True,
        random=False,
        **overrides,
    ):
        c = self.c
        ports = {
            "i_rstb": rstb,
            "i_clock_enable": enable,
            "i_valid": valid,
            "i_lane_enable": lane,
            "i_predicate_enable": pred_enable,
            "i_execute_predicate": execute,
            "i_select_predicate": select,
            "i_opcode": op,
            "i_operand_a": a & c.mask,
            "i_operand_b": b & c.mask,
            "i_accumulator": accumulator % (1 << c.accumulator),
            "i_signed": signed,
            "i_saturate": saturate,
        }
        ports.update(overrides)
        item = LaneItem(
            label, {k: bits(v, c.widths[k]) for k, v in ports.items()}, edge=edge, random=random
        )
        await self.start_item(item)
        await self.finish_item(item)

    async def reset(self, label="reset", *, edge=True):
        await self.cycle(label, valid=0, enable=0, rstb=0, edge=edge)

    async def drain(self):
        for _ in range(self.c.latency + 2):
            await self.cycle("drain", valid=0)

    async def numerical(self):
        c = self.c
        values = sorted({0, 1, c.mask, 1 << (c.element - 1), (1 << (c.element - 1)) - 1})
        acc_values = {
            0,
            1,
            (1 << c.accumulator) - 1,
            1 << (c.accumulator - 1),
            (1 << (c.accumulator - 1)) - 1,
        }
        for op, signed, sat, a, b in product(range(32), range(2), range(2), values, values):
            await self.cycle("boundaries", op=op, signed=signed, saturate=sat, a=a, b=b)
        for signed, sat, a, b, accumulator in product(
            range(2), range(2), values, values, acc_values
        ):
            await self.cycle(
                "mac_boundaries",
                op=21,
                signed=signed,
                saturate=sat,
                a=a,
                b=b,
                accumulator=accumulator,
            )
        for op, lane, pe, ex in product(range(32), range(2), range(2), range(2)):
            await self.cycle("predication", op=op, lane=lane, pred_enable=pe, execute=ex)
        for select, equal in product(range(2), range(2)):
            await self.cycle("select", op=15, select=select, a=0, b=0 if equal else 1)
        for op, amount in product(
            (6, 7, 8), {0, 1, c.element - 1, c.element, c.element + 1, c.mask}
        ):
            if amount <= c.mask:
                await self.cycle("shift_amount", op=op, a=c.mask, b=amount)
        if c.element <= 2:
            for op, signed, sat, a, b in product(
                range(22), range(2), range(2), range(1 << c.element), range(1 << c.element)
            ):
                await self.cycle(
                    "exhaustive",
                    op=op,
                    signed=signed,
                    saturate=sat,
                    a=a,
                    b=b,
                    accumulator=(a * b + a) % (1 << c.accumulator),
                )

    async def unknowns(self):
        c = self.c
        for state in "xz":
            bad = {
                "i_opcode": state * 5,
                "i_operand_a": state * c.element,
                "i_operand_b": state * c.element,
                "i_accumulator": state * c.accumulator,
                "i_signed": state,
                "i_saturate": state,
                "i_select_predicate": state,
            }
            await self.cycle(
                "ignored_unknowns",
                valid=0,
                i_lane_enable=state,
                i_predicate_enable=state,
                i_execute_predicate=state,
                **bad,
            )
            await self.cycle(
                "ignored_unknowns",
                lane=0,
                i_predicate_enable=state,
                i_execute_predicate=state,
                **bad,
            )
            await self.cycle("ignored_unknowns", pred_enable=1, execute=0, **bad)
            await self.cycle(
                "ignored_unknowns",
                op=16,
                i_operand_b=state * c.element,
                i_accumulator=state * c.accumulator,
                i_execute_predicate=state,
                i_select_predicate=state,
            )
            await self.cycle("ignored_unknowns", op=17, i_operand_a=state * c.element)
            await self.cycle("ignored_unknowns", op=15, select=1, i_operand_b=state * c.element)
            await self.cycle("ignored_unknowns", op=15, select=0, i_operand_a=state * c.element)
            for name in (
                "i_lane_enable",
                "i_predicate_enable",
                "i_execute_predicate",
                "i_opcode",
                "i_signed",
                "i_saturate",
                "i_select_predicate",
            ):
                await self.cycle(
                    "illegal_unknown", op=15, pred_enable=1, **{name: state * c.widths[name]}
                )
            if c.latency:
                await self.cycle("stalled_unknowns", enable=0, valid=state, **bad)
            else:
                await self.cycle("ignored_clock_controls", rstb=state, enable=state, edge=False)
        if not c.latency:
            for rstb, enable in product(range(2), repeat=2):
                await self.cycle("ignored_clock_controls", rstb=rstb, enable=enable, edge=False)

    async def pipeline(self):
        c = self.c
        for previous, current in product(range(32), repeat=2):
            await self.cycle("mixed_paths", op=previous, a=c.mask, b=1)
            await self.cycle("mixed_paths", op=current, a=1, b=c.mask, signed=1)
        for op in (0, 20, 21, 31):
            for occupancy in range(c.latency + 1):
                await self.drain()
                for _ in range(occupancy):
                    await self.cycle("fill_before_reset", op=op)
                await self.reset("clockless_reset", edge=False)
                await self.reset()
                await self.cycle("refill", op=op)
        if not c.latency:
            return
        for occupancy, duration in product({0, 1, c.latency}, (1, 3, 32)):
            await self.drain()
            for index in range(occupancy):
                await self.cycle("fill_before_stall", op=(0, 20, 21)[index % 3])
            for _ in range(duration):
                await self.cycle(
                    "stall",
                    enable=0,
                    op=self.rng.randrange(32),
                    a=self.rng.getrandbits(c.element),
                    b=self.rng.getrandbits(c.element),
                )
            await self.cycle("resume", op=21)

    async def body(self):
        c = self.c
        await self.reset()
        if c.probe:
            name, state, op, select = c.probe.split(":")
            await self.cycle(
                "negative_probe", op=int(op), select=int(select), **{name: state * c.widths[name]}
            )
            raise AssertionError("Native protocol assertion did not fire")
        await self.numerical()
        await self.unknowns()
        await self.pipeline()
        for _ in range(c.random_cycles):
            await self.cycle(
                "random",
                random=True,
                op=self.rng.randrange(32),
                a=self.rng.getrandbits(c.element),
                b=self.rng.getrandbits(c.element),
                accumulator=self.rng.getrandbits(c.accumulator),
                signed=self.rng.randrange(2),
                saturate=self.rng.randrange(2),
                valid=int(self.rng.random() > 0.2),
                lane=int(self.rng.random() > 0.2),
                pred_enable=self.rng.randrange(2),
                execute=self.rng.randrange(2),
                select=self.rng.randrange(2),
                enable=int(self.rng.random() > 0.2),
                rstb=int(self.rng.random() > 0.015),
            )
        await self.drain()
