"""Directed and seeded dff sequences."""

from itertools import product
import random
from pyuvm import uvm_sequence
from dff.transaction import DffItem, Inputs


class DffSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("dff_sequence")
        self.config = config

    async def send(self, label, clk, rstb, enable, data, *, unknown=None):
        item = DffItem(label, Inputs(clk, rstb, enable, data), unknown=unknown)
        await self.start_item(item)
        await self.finish_item(item)

    async def cycle(self, label, data, *, rstb=1, enable=1, unknown=None):
        # Controls settle a full phase before the rising edge. High-phase data
        # and enable activity must not update state or create an internal clock.
        changed_data = data ^ self.config.maximum if isinstance(data, int) else "0" * self.config.width
        changed_enable = 1 - enable if isinstance(enable, int) else enable
        await self.send(label + "_setup", 0, rstb, enable, data, unknown=unknown)
        await self.send(label + "_rise", 1, rstb, enable, data, unknown=unknown)
        await self.send(label + "_high_activity", 1, rstb, changed_enable, changed_data, unknown=unknown)
        await self.send(label + "_fall", 0, rstb, changed_enable, changed_data, unknown=unknown)

    async def body(self):
        config, maximum = self.config, self.config.maximum
        await self.cycle("initial_reset", maximum, rstb=0, enable=0)
        # All priority combinations include data different from the reset value.
        for enable, data in product((0, 1), (0, maximum, config.reset_value ^ maximum)):
            await self.cycle("before_priority_reset", config.reset_value ^ maximum)
            await self.cycle("reset_priority", data, rstb=0, enable=enable)
            await self.cycle("reset_release_hold", maximum, enable=0)
        for unknown in ("x", "z"):
            await self.cycle("reset_masks_enable", maximum, rstb=0, enable=unknown)

        # A reset pulse entirely between rising edges distinguishes sync/async
        # implementations. Exercise assertions while both clock levels are held.
        for phase, clk in (("low", 0), ("high", 1)):
            await self.cycle("before_short_reset", config.reset_value ^ maximum)
            await self.send("pulse_prepare", 0, 1, 0, config.reset_value ^ maximum)
            if clk:
                await self.send("pulse_hold_rise", 1, 1, 0, config.reset_value ^ maximum)
            await self.send(f"short_reset_assert_{phase}", clk, 0, 0, maximum)
            await self.send(f"short_reset_input_activity_{phase}", clk, 0, 1, 0)
            await self.send(f"short_reset_release_{phase}", clk, 1, 0, maximum)
            await self.send("pulse_end_low", 0, 1, 0, maximum)
            await self.cycle("after_short_reset", 0, enable=0)

        # Long runs and alternating cycles cover the enable/state-update rules.
        for index in range(32):
            await self.cycle("consecutive_capture", maximum if index % 2 else 0)
        for index in range(32):
            await self.cycle("consecutive_hold", maximum if index % 2 else 0, enable=0)
        for index in range(32):
            await self.cycle("alternating_enable", maximum if index % 2 else 0, enable=index % 2)
        # Walking one/zero patterns explicitly exercise every lane, even at 128 bits.
        for bit in range(config.width):
            await self.cycle("walking_one", 1 << bit)
            await self.cycle("walking_zero", maximum ^ (1 << bit))
        if not config.has_enable:
            for enable in (0, 1, "x", "z"):
                await self.cycle("ignored_enable", maximum, enable=enable)
                await self.cycle("ignored_enable", 0, enable=enable)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            await self.cycle(f"random_{index}", rng.getrandbits(config.width),
                             rstb=int(rng.randrange(16) != 0), enable=rng.randrange(2))

        # These illegal controls are expected assertion diagnostics, never valid
        # numeric transactions. Reset re-establishes known state after each case.
        for value, enable in product(("x", "z"), (0, 1)):
            await self.cycle("before_unknown_reset", maximum, rstb=0)
            await self.cycle("unknown_reset", maximum, rstb=value, enable=enable, unknown=("rstb", value))
            await self.cycle("recover_unknown_reset", 0, rstb=0)
        if config.has_enable:
            for value in ("x", "z"):
                await self.cycle("before_unknown_enable", maximum, rstb=0)
                await self.cycle("unknown_enable", maximum, enable=value, unknown=("enable", value))
                await self.cycle("recover_unknown_enable", 0, rstb=0)
        await self.cycle("final_capture", 0)
        await self.cycle("final_hold", maximum, enable=0)
