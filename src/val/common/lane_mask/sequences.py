"""Directed and seeded lane_mask sequences."""

from itertools import product
import random
from pyuvm import uvm_sequence
from lane_mask.constants import SOURCES
from lane_mask.transaction import Inputs, LaneMaskItem
from mosaic_uvm.logic import bits


class LaneMaskSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("lane_mask_sequence")
        self.config = config

    async def send(self, label, operation, valid, mask, predicate, *, negative=False):
        inputs = Inputs(operation, valid, mask, predicate)
        # Negative-test intent is derived from stimulus, independently of the
        # monitor's actual-port known-control checks. Unexpected X/Z still fail.
        expected_unknown = []
        if negative:
            if bits(operation, 1) in ("x", "z"):
                expected_unknown.append("i_operation_valid")
            if bits(operation, 1) == "1":
                expected_unknown.extend(name for name, value in zip(SOURCES, (valid, mask, predicate), strict=True)
                                        if any(char in bits(value, self.config.lanes) for char in "xz"))
        await self.start_item(item := LaneMaskItem(label, inputs, expected_unknown=tuple(expected_unknown)))
        await self.finish_item(item)

    async def body(self):
        config = self.config
        maximum = config.maximum
        await self.send("simultaneous_clear", 0, 0, 0, 0)
        await self.send("simultaneous_set", 1, maximum, maximum, maximum)
        await self.send("simultaneous_clear_again", 0, 0, 0, 0)

        for lane, source in product(range(config.lanes), range(3)):
            values = [maximum] * 3
            await self.send("independence_baseline", 1, *values)
            values[source] ^= 1 << lane
            await self.send("single_source_disable", 1, *values)
            values[source] ^= 1 << lane
            await self.send("single_source_enable", 1, *values)

        for pattern in config.patterns:
            for source in range(3):
                values = [maximum] * 3
                values[source] = pattern
                await self.send("directed_mask_pattern", 1, *values)
                await self.send("invalid_operation_pattern", 0, *values)
            await self.send("all_sources_pattern", 1, pattern, pattern, pattern)

        # Complete vector truth tables at small sizes, and per-lane truth tables
        # at every size. Other lanes stay active to expose cross-lane coupling.
        if config.lanes <= 4:
            for values in product(range(2), *(range(maximum + 1),) * 3):
                await self.send("exhaustive_binary", *values)
        if config.lanes <= 2:
            words = tuple("".join(word) for word in product("01xz", repeat=config.lanes))
            for values in product("01xz", words, words, words):
                await self.send("exhaustive_four_state_vectors", *values, negative=True)
        for lane in range(config.lanes):
            for operation, *controls in product("01xz", repeat=4):
                vectors = []
                for control in controls:
                    word = ["1"] * config.lanes
                    word[config.lanes - lane - 1] = control
                    vectors.append("".join(word))
                await self.send("per_lane_four_state", operation, *vectors, negative=True)

        # For wide vectors, the finite directed mask set is crossed in full;
        # this is not an exhaustive cross of all 2**LANES possible vectors.
        for first, second in product(config.patterns, repeat=2):
            await self.send("valid_mask_cross", 1, first, second, maximum)
            await self.send("mask_predicate_cross", 1, maximum, first, second)
        for before, after in product(range(config.lanes + 1), repeat=2):
            await self.send("population_before", 1, maximum, (1 << before) - 1, maximum)
            await self.send("population_after", 1, maximum, (1 << after) - 1, maximum)

        # Hold controls through short and long intervals. There is no stall
        # interface here; mask/data alignment during stalls needs a consumer.
        for pattern in (0, maximum, 1, maximum ^ 1):
            for _ in range(32):
                await self.send("stable_hold", 1, maximum, pattern, maximum)
        for operation in (0, 1):
            for value in ("x", "z"):
                await self.send("unknown_all_lane_controls", operation, *(value * config.lanes,) * 3, negative=True)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            operation = rng.choice((0, 0, 1, 1, 1, 1, "x", "z"))
            vectors = []
            for _ in SOURCES:
                word = list(f"{rng.getrandbits(config.lanes):0{config.lanes}b}")
                if rng.randrange(4) == 0:
                    word[rng.randrange(config.lanes)] = rng.choice(("x", "z"))
                vectors.append("".join(word))
            await self.send(f"random_{index}", operation, *vectors, negative=True)
        await self.send("final_invalid_operation", 0, maximum, maximum, maximum)
