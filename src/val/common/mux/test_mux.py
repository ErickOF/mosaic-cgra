"""Specification-driven mux selection, data activity, and fail-closed tests."""

from __future__ import annotations

from itertools import product
import random

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from mux_env import Inputs, MuxConfig, MuxEnv, MuxItem


class MuxSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("mux_sequence")
        self.config = config

    async def send(self, label, select, words, *, hold_ns=0.001):
        item = MuxItem(label, Inputs(select, tuple(words)), hold_ns=hold_ns)
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        config = self.config
        baseline = [index & config.maximum for index in range(config.num_inputs)]
        invert = str.maketrans("01xz", "10zx")
        for selected in range(config.num_inputs):
            words = baseline.copy()
            await self.send("distinct_words", selected, words)
            for pattern in config.patterns:
                words[selected] = pattern
                await self.send("selected_pattern", selected, words)
                words[selected] = pattern.translate(invert)
                await self.send("selected_input_activity", selected, words)
                words[selected] = pattern
                await self.send("return_selected_pattern", selected, words)
            if config.data_width <= 8:
                for value in range(config.maximum + 1):
                    words[selected] = value
                    await self.send("exhaustive_selected_binary", selected, words)
            if config.data_width <= 2:
                for word in product("01xz", repeat=config.data_width):
                    words[selected] = "".join(word)
                    await self.send("exhaustive_selected_four_state", selected, words)

            # Only unselected words change; both outputs must remain inactive
            # throughout each change, including finite pre-sample glitches.
            words = baseline.copy()
            words[selected] = config.default_value ^ config.maximum
            await self.send("unselected_activity_baseline", selected, words)
            for other in range(config.num_inputs):
                if other == selected:
                    continue
                for value in (0, config.maximum, "x" * config.data_width, "z" * config.data_width, 0, config.maximum):
                    words[other] = value
                    await self.send("unselected_input_activity", selected, words)
            await self.send("long_stable_selection", selected, words, hold_ns=1)

        # Explicitly cover every ordered legal pair, including repeated indices.
        for before, after in product(range(config.num_inputs), repeat=2):
            await self.send("legal_pair_before", before, baseline)
            await self.send("legal_pair_after", after, baseline)
        for legal, invalid in product(range(config.num_inputs), config.invalid_encodings):
            await self.send("before_invalid", legal, baseline)
            await self.send("invalid_encoding", invalid, baseline)
            await self.send("recover_legal", legal, baseline)

        # Every four-state selector word is exercised. Keep invalid/unknown
        # selection fixed while corrupting all data words; the default is known.
        for select in (*config.invalid_encodings, *config.unknown_selects):
            await self.send("invalid_selection_baseline", select, baseline)
            for value in (0, config.maximum, "x" * config.data_width, "z" * config.data_width, 0):
                await self.send("invalid_selection_data_activity", select, [value] * config.num_inputs)
            await self.send("invalid_selection_long_hold", select, [0] * config.num_inputs, hold_ns=1)
            await self.send("recover_from_unknown", 0, baseline)

        # Even the single-input instance has a second (invalid) binary encoding.
        await self.send("simultaneous_before", 0, [0] * config.num_inputs)
        await self.send("simultaneous_after", (1 << config.select_width) - 1, [config.maximum] * config.num_inputs)
        rng = random.Random(config.seed)
        selectors = tuple(range(1 << config.select_width)) + config.unknown_selects
        for index in range(config.random_cycles):
            select = rng.choice(selectors) if index % 4 == 0 else rng.randrange(1 << config.select_width)
            words = []
            for _ in range(config.num_inputs):
                if index % 7 == 0:
                    word = "".join(rng.choice("01xz") for _ in range(config.data_width))
                else:
                    word = f"{rng.getrandbits(config.data_width):0{config.data_width}b}"
                    if index % 7 == 1:
                        offset = rng.randrange(config.data_width)
                        word = word[:offset] + rng.choice("xz") + word[offset + 1:]
                words.append(word)
            await self.send(f"random_{index}", select, words)
        await self.send("final_known_selection", 0, baseline, hold_ns=1)


@test(timeout_time=1, timeout_unit="ms")
class MuxTest(uvm_test):
    def build_phase(self):
        self.config = MuxConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == self.config.num_inputs * self.config.data_width
        assert len(cocotb.top.o_data) == self.config.data_width
        assert len(cocotb.top.i_select) == self.config.select_width
        assert len(cocotb.top.o_select_valid) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {
            "item": None, "sample": Event(), "stage": "settled", "kind": "stable", "quiet": False,
        })
        self.env = MuxEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_data.value = 0
        cocotb.top.i_select.value = 0
        await MuxSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
