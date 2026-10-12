"""Directed and seeded operand_isolation sequences."""

from itertools import product
import os
import random
from pyuvm import uvm_sequence
from operand_isolation.transaction import Inputs, OperandIsolationItem


class OperandIsolationSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("operand_isolation_sequence")
        self.config = config

    async def send(self, label, data, control, *, hold_ns=0.001, expect_unknown=True):
        expected = control if expect_unknown and control in ("x", "z") else None
        item = OperandIsolationItem(label, Inputs(data, control), expected_unknown=expected, hold_ns=hold_ns)
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        config = self.config
        # These two deliberately untagged probes must fail the live assertion.
        # Ordinary runs never enable this internal regression diagnostic.
        probe = os.getenv("OPERAND_ISOLATION_CONTROL_PROBE", "")
        if probe:
            assert probe in ("x", "z"), "Unknown-control probe must be x or z"
            await self.send("unexpected_unknown_control", 0, probe, expect_unknown=False)
            return
        invert = str.maketrans("01xz", "10zx")
        for data in config.patterns:
            await self.send("transparent_pattern", data, 0)
            await self.send("assert_stable_data", data, 1)
            await self.send("isolated_data_activity", data.translate(invert), 1)
            await self.send("isolated_return", data, 1)
            await self.send("release_stable_data", data, 0)
            await self.send("transparent_data_activity", data.translate(invert), 0)

        # Isolate each bit's ordered four-state transitions in a known background.
        # Repeating the old value also covers unchanged data and detects state.
        for bit, background, before, after in product(range(config.width), "01", "01xz", "01xz"):
            old, new = [background] * config.width, [background] * config.width
            old[config.width - bit - 1], new[config.width - bit - 1] = before, after
            await self.send("transparent_bit_before", "".join(old), 0)
            await self.send("transparent_bit_after", "".join(new), 0)

        # All control transitions, crossed with stable/changing input, include
        # assertion/release and recovery from each illegal control value.
        for before, after, changed in product("01xz", "01xz", (False, True)):
            await self.send("control_transition_before", 0, before)
            await self.send("control_transition_after", config.maximum if changed else 0, after)
        for data, control in product(config.patterns, "xz"):
            await self.send("unknown_control", data, control)
            await self.send("fixed_unknown_data_activity", data.translate(invert), control)
            await self.send("recover_transparent", data, 0)

        if config.width <= 8:
            for data, control in product(range(config.maximum + 1), (0, 1)):
                await self.send("exhaustive_binary", data, control)
        if config.width <= 2:
            for word, control in product(product("01xz", repeat=config.width), "01xz"):
                await self.send("exhaustive_four_state", "".join(word), control)
        for control in (0, 1, 0, 1, 0):
            await self.send("back_to_back_control", config.maximum, control)
        for control in (0, 1):
            for index in range(64):
                await self.send("long_mode_activity", config.maximum if index % 2 else 0, control, hold_ns=1)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            control = rng.choice((0, 0, 0, 1, 1, 1, "x", "z"))
            if index % 7 == 0:
                data = "".join(rng.choice("01xz") for _ in range(config.width))
            else:
                data = f"{rng.getrandbits(config.width):0{config.width}b}"
                if index % 7 == 1:
                    bit = rng.randrange(config.width)
                    data = data[:bit] + rng.choice("xz") + data[bit + 1:]
            await self.send(f"random_{index}", data, control)
        await self.send("final_transparent", config.maximum, 0, hold_ns=1)
        await self.send("final_isolated", 0, 1, hold_ns=1)
