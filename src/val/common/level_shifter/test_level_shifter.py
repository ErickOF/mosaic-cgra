"""Specification-driven four-state stimulus for both static voltage directions."""

from __future__ import annotations

from itertools import product
import random

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from level_shifter_env import LevelShifterConfig, LevelShifterEnv, LevelShifterItem


class LevelShifterSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("level_shifter_sequence")
        self.config = config

    async def send(self, label, data, *, hold_ns=0.001):
        item = LevelShifterItem(label, data, hold_ns=hold_ns)
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        config = self.config
        invert = str.maketrans("01xz", "10zx")
        for pattern in config.patterns:
            await self.send("directed_pattern", pattern)
            await self.send("rapid_pattern_change", pattern.translate(invert))
            await self.send("revisit_pattern", pattern)
        if config.width <= 8:
            for value in range(config.maximum + 1):
                await self.send("exhaustive_binary", value)
        if config.width <= 4:
            for word in product("01xz", repeat=config.width):
                await self.send("exhaustive_four_state", "".join(word))

        # Each bit changes independently through every ordered four-state pair
        # on both known backgrounds, including stable diagonal transitions.
        for bit, background, before, after in product(range(config.width), "01", "01xz", "01xz"):
            word = [background] * config.width
            offset = config.width - bit - 1
            word[offset] = before
            await self.send("independent_bit_before", "".join(word))
            word[offset] = after
            await self.send("independent_bit_after", "".join(word))

        for value in (0, config.maximum, "x" * config.width, "z" * config.width):
            await self.send("long_stable", value, hold_ns=4)
            for _ in range(16):
                await self.send("short_stable", value)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            if index % 5 == 0:
                # Independent activity includes mixed known and unknown bits.
                word = "".join(rng.choice("01xz") for _ in range(config.width))
            else:
                word = f"{rng.getrandbits(config.width):0{config.width}b}"
                if index % 5 == 1:
                    offset = rng.randrange(config.width)
                    word = word[:offset] + rng.choice("xz") + word[offset + 1:]
            await self.send(f"random_{index}", word)
        await self.send("final_known_value", config.maximum, hold_ns=1)


@test(timeout_time=1, timeout_unit="ms")
class LevelShifterTest(uvm_test):
    def build_phase(self):
        self.config = LevelShifterConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == len(cocotb.top.o_data) == self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {
            "item": None, "sample": Event(), "stage": "settled", "stable": False,
        })
        self.env = LevelShifterEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_data.value = 0
        await LevelShifterSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
