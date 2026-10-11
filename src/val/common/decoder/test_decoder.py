"""Exhaustive encodings, legal transition pairs, and four-state PyUVM stimulus."""

from __future__ import annotations

from itertools import product
import random

import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from decoder_env import DecoderConfig, DecoderEnv, DecoderItem, Inputs


class DecoderSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("decoder_specification_sequence")
        self.config = config

    async def send(self, label, enable, select):
        item = DecoderItem(label, Inputs(enable, select))
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        config = self.config
        await self.send("initial_disabled", 0, 0)
        for selected in config.encodings:
            await self.send("disabled_encoding", 0, selected)
        for selected in config.encodings:
            await self.send("enabled_encoding", 1, selected)
        for source, destination in product(range(config.num_outputs), repeat=2):
            await self.send("legal_pair_source", 1, source)
            await self.send("legal_pair_destination", 1, destination)
        for legal, invalid in product(range(config.num_outputs), config.invalid_encodings):
            await self.send("legal_before_invalid", 1, legal)
            await self.send("invalid_after_legal", 1, invalid)
            await self.send("legal_after_invalid", 1, legal)
        for selected in config.encodings:
            await self.send("enable_baseline", 0, selected)
            await self.send("enable_assertion", 1, selected)
            await self.send("enable_deassertion", 0, selected)
        await self.send("simultaneous_baseline", 1, 0)
        await self.send("simultaneous_disable_and_selection", 0, 1)
        await self.send("simultaneous_enable_and_selection", 1, 0)

        # Check each unknown enable against every binary selection, including
        # invalid encodings. Fail-closed behavior is specified, not illegal.
        for unknown, selected in product(("x", "z"), config.encodings):
            await self.send("known_before_unknown_enable", 1, selected % config.num_outputs)
            await self.send(f"unknown_enable_{unknown}", unknown, selected)
        for enable, unknown in product((0, 1), ("x", "z")):
            for position, fill in product(range(config.select_width), ("0", "1")):
                bits = list(fill * config.select_width)
                bits[position] = unknown
                await self.send("known_before_unknown_selection", 1, 0)
                await self.send("single_unknown_selection_bit", enable, "".join(bits))
            await self.send("all_unknown_selection", enable, unknown * config.select_width)
        if config.select_width > 1:
            mixed = "".join("x" if index % 2 == 0 else "z" for index in range(config.select_width))
            for enable in (0, 1):
                await self.send("mixed_unknown_selection", enable, mixed)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            enable = rng.randrange(2)
            select = rng.randrange(len(config.encodings))
            if rng.randrange(16) == 0:
                enable = rng.choice(("x", "z"))
            if rng.randrange(16) == 0:
                bits = list(f"{select:0{config.select_width}b}")
                bits[rng.randrange(config.select_width)] = rng.choice(("x", "z"))
                select = "".join(bits)
            await self.send(f"random_{index}", enable, select)
        # Selection activity while continuously disabled must have no output
        # transitions, not merely zero at the sampling points.
        await self.send("final_disabled_baseline", 0, 0)
        for selected in (*config.encodings, *reversed(config.encodings)):
            await self.send("disabled_selection_sweep", 0, selected)
        await self.send("final_known_disabled", 0, 0)


@test(timeout_time=1, timeout_unit="ms")
class DecoderTest(uvm_test):
    def build_phase(self):
        self.config = DecoderConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.o_decoded) == self.config.num_outputs, "NUM_OUTPUTS override was not applied"
        assert len(cocotb.top.i_select) == self.config.select_width, "SELECT_WIDTH must be derived from NUM_OUTPUTS"
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "sample": Event(), "quiet": False})
        self.env = DecoderEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_enable.value = 0
        cocotb.top.i_select.value = 0
        await DecoderSequence(self.config).start(self.env.sequencer)
        self.drop_objection()
