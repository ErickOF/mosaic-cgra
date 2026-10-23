"""Mask, numerical, exhaustive, stall/reset and reproducible random sequences."""

import random
from itertools import product

from mosaic_uvm.logic import bits
from pyuvm import uvm_sequence

from vector_reduction.transaction import ReductionItem


def masks(c):
    full = (1 << c.count) - 1
    alternating = sum(1 << k for k in range(0, c.count, 2))
    return sorted(
        {
            0,
            full,
            alternating,
            full ^ alternating,
            *(1 << k for k in range(c.count)),
            *(full ^ (1 << k) for k in range(c.count)),
            *((1 << n) - 1 for n in range(c.count + 1)),
        }
    )


def boundary_vectors(c):
    values = sorted({0, 1, c.mask, 1 << (c.element - 1), (1 << (c.element - 1)) - 1})
    vectors = {tuple([v] * c.count) for v in values}
    for a, b in product(values, repeat=2):
        vectors.add(tuple(a if k % 2 else b for k in range(c.count)))
        for k in range(c.count):
            vectors.add(tuple(a if k == index else b for index in range(c.count)))
    vectors.add(tuple(k & c.mask for k in range(c.count)))
    vectors.add(tuple((c.count - k - 1) & c.mask for k in range(c.count)))
    return sorted(vectors)


class ReductionSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("vector_reduction_sequence")
        self.c = config
        self.rng = random.Random(config.seed)

    async def cycle(
        self,
        label,
        *,
        op=0,
        values=None,
        mask=None,
        signed=0,
        valid=1,
        enable=1,
        rstb=1,
        edge=True,
        random=False,
        **overrides,
    ):
        c = self.c
        values = [1] * c.count if values is None else values
        data = sum((value & c.mask) << (k * c.element) for k, value in enumerate(values))
        ports = {
            "i_rstb": rstb,
            "i_clock_enable": enable,
            "i_valid": valid,
            "i_opcode": op,
            "i_element_mask": (1 << c.count) - 1 if mask is None else mask,
            "i_data": data,
            "i_signed": signed,
        }
        ports.update(overrides)
        item = ReductionItem(
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
        for op, signed, mask in product(range(8), range(2), masks(c)):
            await self.cycle("mask_cross", op=op, signed=signed, mask=mask)
        for op, signed, values in product(range(5), range(2), boundary_vectors(c)):
            await self.cycle("boundaries", op=op, signed=signed, values=values)
        if c.element * c.count <= 6 and c.count <= 3:
            for data, mask, op, signed in product(
                range(1 << (c.element * c.count)), range(1 << c.count), range(8), range(2)
            ):
                await self.cycle("exhaustive", op=op, signed=signed, mask=mask, i_data=data)
        # Every SUM prefix and alternating opposite signs test width growth/cancellation.
        for count, signed in product(range(c.count + 1), range(2)):
            for value in (c.mask, 1 << (c.element - 1)):
                await self.cycle(
                    "sum_growth",
                    op=0,
                    signed=signed,
                    mask=(1 << count) - 1,
                    values=[value] * c.count,
                )

    async def unknowns(self):
        c = self.c
        for state in "xz":
            await self.cycle(
                "ignored_unknowns",
                valid=0,
                i_opcode=state * 3,
                i_element_mask=state * c.count,
                i_signed=state,
                i_data=state * (c.element * c.count),
            )
            for op in range(8):
                await self.cycle(
                    "ignored_unknowns", op=op, mask=0, i_data=state * (c.element * c.count)
                )
            for op, k in product(range(5), range(c.count)):
                # Only selected slices are known; all others deliberately contain X/Z.
                words = [state * c.element] * c.count
                words[k] = bits(c.mask, c.element)
                await self.cycle(
                    "masked_unknowns", op=op, mask=1 << k, i_data="".join(reversed(words))
                )
            for name in ("i_opcode", "i_element_mask", "i_signed"):
                await self.cycle("illegal_unknowns", **{name: state * c.widths[name]})
            if c.latency:
                await self.cycle(
                    "stalled_unknowns",
                    enable=0,
                    i_valid=state,
                    i_opcode=state * 3,
                    i_element_mask=state * c.count,
                    i_signed=state,
                    i_data=state * (c.element * c.count),
                )
            else:
                await self.cycle("ignored_clock_controls", rstb=state, enable=state, edge=False)
        if not c.latency:
            for rstb, enable in product(range(2), repeat=2):
                await self.cycle("ignored_clock_controls", rstb=rstb, enable=enable, edge=False)

    async def timing(self):
        c = self.c
        for previous, current in product(range(8), repeat=2):
            await self.cycle("mixed_operations", op=previous)
            await self.cycle("mixed_operations", op=current, signed=1)
        if not c.latency:
            return
        for op, occupancy in product(range(5), range(c.latency + 1)):
            await self.drain()
            for _ in range(occupancy):
                await self.cycle("fill_before_reset", op=op)
            await self.reset("clockless_reset", edge=False)
            await self.reset()
            await self.cycle("refill", op=op)
        for occupancy, duration in product({0, 1, c.latency}, (1, 3, 32)):
            await self.drain()
            for index in range(occupancy):
                await self.cycle("fill_before_stall", op=index % 5)
            for _ in range(duration):
                await self.cycle(
                    "stall",
                    enable=0,
                    op=self.rng.randrange(8),
                    values=[self.rng.getrandbits(c.element) for _ in range(c.count)],
                )
            await self.cycle("resume")

    async def body(self):
        c = self.c
        await self.reset()
        if c.probe:
            kind, index, state = c.probe.split(":")
            if kind in ("opaque_and", "opaque_or"):
                op = 3 if kind == "opaque_and" else 4
                value = 0 if op == 3 else c.mask
                await self.cycle("opaque_warmup", op=op, values=[value] * c.count)
                words = [bits(value, c.element)] * c.count
                words[0] = state * c.element
                await self.cycle("negative_probe", op=op, i_data="".join(reversed(words)))
            elif kind == "element":
                k = int(index)
                word = [bits(1, c.element)] * c.count
                word[k] = state * c.element
                await self.cycle("negative_probe", op=k % 5, i_data="".join(reversed(word)))
            else:
                await self.cycle("negative_probe", **{kind: state * c.widths[kind]})
            raise AssertionError("Native protocol assertion did not fire")
        await self.numerical()
        await self.unknowns()
        await self.timing()
        for _ in range(c.random_cycles):
            await self.cycle(
                "random",
                random=True,
                op=self.rng.randrange(8),
                values=[self.rng.getrandbits(c.element) for _ in range(c.count)],
                mask=self.rng.getrandbits(c.count),
                signed=self.rng.randrange(2),
                valid=int(self.rng.random() > 0.2),
                enable=int(self.rng.random() > 0.2),
                rstb=int(self.rng.random() > 0.015),
            )
        await self.drain()
