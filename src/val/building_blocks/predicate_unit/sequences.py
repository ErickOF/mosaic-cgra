"""Directed stateful traces, exhaustive small banks and seeded command streams."""

import random
from itertools import product

from mosaic_uvm.logic import bits
from pyuvm import uvm_sequence

from predicate_unit.transaction import INPUTS, PredicateItem


class PredicateSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("predicate_sequence")
        self.c = config
        self.rng = random.Random(config.seed)
        self.serial = 0

    async def send(
        self, label, *, edge=True, random=False, exhaustive=False, **changes
    ):
        values = (
            dict.fromkeys(INPUTS, 0)
            | {
                "i_rstb": 1,
                "i_clock_enable": 1,
                "i_valid": 1,
                "i_lane_mask": self.c.mask,
            }
            | changes
        )
        item = PredicateItem(
            f"{self.serial}:{label}",
            {key: bits(value, self.c.widths[key]) for key, value in values.items()},
            edge=edge,
            random=random,
        )
        item.exhaustive = exhaustive
        self.serial += 1
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def load(self, entry, value, mask=None):
        return await self.send(
            "initialize",
            i_opcode=2,
            i_write_enable=1,
            i_destination_addr=entry,
            i_predicate_input=value,
            i_lane_mask=self.c.mask if mask is None else mask,
        )

    async def initialize(self):
        for entry in range(self.c.depth):
            await self.load(entry, (self.c.mask // 3) ^ (entry & self.c.mask))

    async def reset(self, label):
        await self.send(label, edge=False, i_rstb=0, i_clock_enable=0)
        await self.send(label, i_rstb=0, i_clock_enable=0)
        await self.send("reset_release", edge=False, i_valid=0)

    async def probe(self):
        c = self.c
        await self.initialize()
        name, state = c.probe.split(":")
        change = {"i_opcode": 2, "i_write_enable": 1}
        if name.startswith("load"):
            lane = int(name.removeprefix("load"))
            word = list("0" * c.lanes)
            word[-1 - lane] = state
            change["i_predicate_input"] = "".join(word)
        else:
            change[name] = state
        await self.send("assertion_probe", **change)
        raise AssertionError("Native protocol checker did not reject the probe")

    async def exhaustive(self):
        c = self.c
        if c.depth * c.lanes > 2:
            return
        # Each lane has the three architecturally distinguishable states:
        # invalid, valid false and valid true. Restore the entire pre-state for
        # EACH candidate so writeback/invalidation cannot bias later commands.
        addresses = range(1 << c.address_width)
        for state in product(range(3), repeat=c.depth * c.lanes):
            for op, mask, a, b, dest, data, write in product(
                range(16),
                range(c.mask + 1),
                addresses,
                addresses,
                addresses,
                range(c.mask + 1),
                range(2),
            ):
                for entry in range(c.depth):
                    await self.send(
                        "restore_invalid",
                        i_opcode=8,
                        i_write_enable=1,
                        i_destination_addr=entry,
                    )
                    row = state[entry * c.lanes : (entry + 1) * c.lanes]
                    valid = sum((value != 0) << k for k, value in enumerate(row))
                    payload = sum((value == 2) << k for k, value in enumerate(row))
                    if valid:
                        await self.load(entry, payload, valid)
                await self.send(
                    "exhaustive",
                    exhaustive=True,
                    i_opcode=op,
                    i_lane_mask=mask,
                    i_source_a_addr=a,
                    i_source_b_addr=b,
                    i_destination_addr=dest,
                    i_predicate_input=data,
                    i_write_enable=write,
                )

    async def body(self):
        c, rng = self.c, self.rng
        await self.reset("reset_empty")
        if c.probe:
            await self.probe()
            return
        # Invalid cycles must ignore ALL request fields, including X and Z.
        for state in "xz":
            await self.send(
                "ignored_invalid",
                i_valid=0,
                **{
                    key: state * c.widths[key]
                    for key in INPUTS
                    if key not in ("i_rstb", "i_clock_enable", "i_valid")
                },
            )
        await self.initialize()
        masks = sorted(
            {
                0,
                c.mask,
                c.mask // 3,
                c.mask ^ (c.mask // 3),
                *(1 << k for k in range(c.lanes)),
                *((1 << k) - 1 for k in range(c.lanes + 1)),
            }
        )
        for op, mask, write in product(range(16), masks, range(2)):
            await self.initialize()
            await self.send(
                "opcode_mask_write",
                i_opcode=op,
                i_lane_mask=mask,
                i_write_enable=write,
                i_predicate_input=rng.getrandbits(c.lanes),
                i_source_a_addr=0,
                i_source_b_addr=c.depth - 1,
                i_destination_addr=c.depth - 1,
            )
        # Close previous/next command and summary-population crosses explicitly.
        for population in range(c.lanes + 1):
            mask = (1 << population) - 1
            for value in (0, mask, mask & ~1):
                await self.send(
                    "summary", i_opcode=2, i_lane_mask=mask, i_predicate_input=value
                )
        for first, second in product(range(9), repeat=2):
            await self.initialize()
            await self.send("dependent_first", i_opcode=first, i_write_enable=1)
            await self.send("dependent_next", i_opcode=second, i_write_enable=1)
        # Every address and alias combination, immediately followed by recurrence.
        await self.initialize()
        for op, a, b, dest in product(
            range(3, 8), range(c.depth), range(c.depth), range(c.depth)
        ):
            await self.send(
                "aliases",
                i_opcode=op,
                i_source_a_addr=a,
                i_source_b_addr=b,
                i_destination_addr=dest,
                i_write_enable=1,
            )
            await self.send("dependent", i_opcode=3, i_source_a_addr=dest)
        for op in range(9):
            for entry in range(c.depth):
                for pin in ("i_source_a_addr", "i_source_b_addr", "i_destination_addr"):
                    await self.initialize()
                    await self.send(
                        "individual_address",
                        i_opcode=op,
                        i_write_enable=1,
                        **{pin: entry},
                    )
        # Global controls, required/ignored X/Z addresses, unused encodings.
        for pin in ("i_opcode", "i_lane_mask", "i_write_enable"):
            for state in "xz":
                await self.send("unknown_control", **{pin: state * c.widths[pin]})
        await self.initialize()
        bad_addresses = [
            *range(c.depth, 1 << c.address_width),
            "x" * c.address_width,
            "z" * c.address_width,
        ]
        for pin, address, op, mask, write in product(
            ("i_source_a_addr", "i_source_b_addr", "i_destination_addr"),
            bad_addresses,
            range(9),
            (0, c.mask),
            range(2),
        ):
            await self.initialize()
            await self.send(
                "address_required_ignored",
                i_opcode=op,
                i_lane_mask=mask,
                i_write_enable=write,
                **{pin: address},
            )
        # One invalid selected lane must cancel the WHOLE update, even when an
        # AND-zero or OR-one could determine the result without that source bit.
        for entry, lane, op in product(range(c.depth), range(c.lanes), range(3, 8)):
            for port in ("i_source_a_addr", "i_source_b_addr"):
                await self.initialize()
                await self.send(
                    "invalidate_one",
                    i_opcode=8,
                    i_write_enable=1,
                    i_destination_addr=entry,
                    i_lane_mask=1 << lane,
                )
                other = (
                    "i_source_b_addr"
                    if port == "i_source_a_addr"
                    else "i_source_a_addr"
                )
                await self.send(
                    "atomic_invalid_source",
                    i_opcode=op,
                    i_write_enable=1,
                    **{port: entry, other: (entry + 1) % c.depth},
                )
                await self.send(
                    "masked_invalid_source",
                    i_opcode=op,
                    i_write_enable=1,
                    i_lane_mask=c.mask ^ (1 << lane),
                    **{port: entry, other: (entry + 1) % c.depth},
                )
        # Unknown LOAD bits are ignored in masked lanes and on all other opcodes.
        for state in "xz":
            for lane in range(c.lanes):
                word = list("0" * c.lanes)
                word[-1 - lane] = state
                await self.send(
                    "masked_unknown_load",
                    i_opcode=2,
                    i_write_enable=1,
                    i_lane_mask=c.mask ^ (1 << lane),
                    i_predicate_input="".join(word),
                )
            await self.send(
                "unused_unknown_data", i_opcode=1, i_predicate_input=state * c.lanes
            )
        # Workload: nested conditions and loop-tail masks, preserve then invalidate.
        await self.initialize()
        for tail in range(c.lanes + 1):
            await self.load(0, (1 << tail) - 1)
            await self.send(
                "context_preserve",
                i_opcode=4,
                i_source_a_addr=0,
                i_write_enable=1,
                i_destination_addr=c.depth - 1,
            )
            await self.send(
                "context_preserve",
                i_opcode=5,
                i_source_a_addr=0,
                i_source_b_addr=c.depth - 1,
            )
        await self.send("context_invalidate", i_opcode=8, i_write_enable=1)
        await self.send("context_stale_read", i_opcode=3)
        # State/response hold through real disabled edges and absent clock edges.
        await self.initialize()
        for op, duration in product(range(9), (1, 2, 5)):
            await self.send("before_stall", i_opcode=op, i_write_enable=1)
            for _ in range(duration):
                await self.send(
                    f"stall_{duration}",
                    i_clock_enable=0,
                    i_opcode=rng.randrange(16),
                    i_write_enable=1,
                    i_predicate_input=rng.getrandbits(c.lanes),
                )
            await self.send("clockless", edge=False, i_opcode=op, i_write_enable=1)
        for population in ("empty", "partial", "full"):
            await self.reset("reset_before_" + population)
            if population == "partial":
                await self.load(0, 1, 1)
            elif population == "full":
                await self.initialize()
            await self.send("valid_response_before_reset", i_opcode=1)
            await self.reset("reset_" + population)
            await self.send("stale_after_reset", i_opcode=3)
        await self.exhaustive()
        for _ in range(c.random_cycles):
            await self.send(
                "random",
                random=True,
                i_opcode=rng.randrange(16),
                i_valid=int(rng.random() > 0.08),
                i_clock_enable=int(rng.random() > 0.12),
                i_lane_mask=rng.getrandbits(c.lanes),
                i_source_a_addr=rng.getrandbits(c.address_width),
                i_source_b_addr=rng.getrandbits(c.address_width),
                i_destination_addr=rng.getrandbits(c.address_width),
                i_write_enable=rng.randrange(2),
                i_predicate_input=rng.getrandbits(c.lanes),
            )
        await self.send("drain", i_valid=0)
