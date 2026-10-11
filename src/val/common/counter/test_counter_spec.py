"""Directed, exhaustive-small-state, random, and four-state PyUVM sequences."""

from __future__ import annotations

from itertools import product
import random

import cocotb
from cocotb.clock import Clock
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from counter_env import CONTROLS, CounterConfig, CounterEnv, CounterItem, Inputs


class CounterSpecSequence(uvm_sequence):
    """Exercise the functional and coverage requirements of mosaic-counter."""

    def __init__(self, config):
        super().__init__("counter_spec_sequence")
        self.config = config

    async def send(self, label, *, unknown=None, pulse_reset=False, **controls):
        item = CounterItem(label, Inputs(**controls), unknown=unknown, pulse_reset=pulse_reset)
        await self.start_item(item)
        await self.finish_item(item)

    async def load(self, value):
        await self.send("load_value", load=1, load_value=value)

    async def body(self):
        config = self.config
        maximum = config.maximum
        await self.send("initial_reset", rstb=0)

        # Cover every priority combination, including reset against every
        # active command and both directions. Load makes the starting state known.
        for controls in product((0, 1), repeat=5):
            await self.load(maximum)
            await self.send(
                "priority_combination", **dict(zip(CONTROLS, controls)),
                load_value=maximum // 2,
            )

        for value in sorted(config.representative_values):
            await self.load(value)
        for value in (0, maximum):
            await self.load(value)
            for direction in (0, 1, 0):
                await self.send("disabled_terminal", direction=direction)

        await self.load(maximum - 1)
        await self.send("increment_to_maximum", enable=1)
        await self.send("overflow", enable=1)
        await self.send("overflow_followed_by_decrement", enable=1, direction=1)
        await self.send("event_clears_on_hold")
        await self.load(1)
        await self.send("decrement_to_zero", enable=1, direction=1)
        await self.send("underflow", enable=1, direction=1)
        await self.send("underflow_followed_by_increment", enable=1)
        await self.send("event_clears_on_hold")

        # Clear an asserted event with each non-arithmetic command. This is
        # directed even for wide counters, where random boundary hits are rare.
        for direction in (0, 1):
            for command, controls in (
                ("hold", {}),
                ("clear", {"clear": 1}),
                ("load", {"load": 1, "load_value": config.reset_value}),
            ):
                await self.load(maximum if direction == 0 else 0)
                await self.send("boundary_before_non_arithmetic", enable=1, direction=direction)
                await self.send(f"event_clears_on_{command}", direction=direction, **controls)

        # Reset must also clear an outstanding boundary event.
        await self.load(maximum)
        await self.send("overflow_before_reset", enable=1)
        await self.send("reset_clears_overflow", rstb=0)
        await self.load(0)
        await self.send("underflow_before_reset", enable=1, direction=1)
        await self.send("reset_clears_underflow", rstb=0)

        # A pulse entirely between rising edges distinguishes the reset modes.
        await self.load(config.reset_value ^ maximum)
        await self.send("short_reset_pulse", rstb=0, pulse_reset=True)
        await self.send("reset_release_hold")

        for direction in (0, 1):
            await self.load(0 if direction == 0 else maximum)
            for _ in range(64):
                await self.send("long_active", enable=1, direction=direction)
        for _ in range(32):
            await self.send("long_hold")

        # For WIDTH<=4, cover every starting count, all command-control
        # combinations, and both directions. Loading avoids reachability bias.
        if config.width <= 4:
            for value in range(maximum + 1):
                for controls in product((0, 1), repeat=5):
                    await self.load(value)
                    await self.send(
                        "exhaustive_state_controls", **dict(zip(CONTROLS, controls)),
                        load_value=(value + 1) & maximum,
                    )

        # Reset-state coverage is exhaustive through WIDTH=8. Exploring every
        # state of 32/64-bit counters requires formal proof, not a finite test.
        reset_values = (
            range(maximum + 1) if config.width <= 8
            else sorted(config.representative_values)
        )
        for value in reset_values:
            await self.load(value)
            await self.send("reset_from_state", rstb=0)

        rng = random.Random(config.seed)
        for cycle in range(config.random_cycles):
            await self.send(
                f"random_{cycle}", rstb=int(rng.randrange(32) != 0),
                clear=int(rng.randrange(16) == 0), load=int(rng.randrange(8) == 0),
                enable=rng.randrange(2), direction=rng.randrange(2),
                load_value=rng.getrandbits(config.width),
            )

        # Illegal controls must be detected. These are expected assertion
        # violations; no numerical behavior is specified for illegal commands.
        for name, unknown in product(CONTROLS, ("x", "z")):
            await self.send("recover_before_unknown", rstb=0)
            controls = {"enable": 1, name: unknown}
            await self.send(f"unknown_{name}_{unknown}", unknown=name, **controls)
            await self.send("recover_after_unknown", rstb=0)
        for unknown in ("x", "z"):
            await self.send(
                f"disabled_unknown_direction_{unknown}", unknown="direction",
                direction=unknown,
            )
            await self.send("recover_after_unknown", rstb=0)
        await self.send("final_hold")


@test(timeout_time=1, timeout_unit="ms")
class CounterSpecTest(uvm_test):
    """Run a real PyUVM sequencer/driver/monitor/scoreboard environment."""

    def build_phase(self):
        self.config = CounterConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.o_count) == self.config.width, "WIDTH override was not applied"
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None})
        self.env = CounterEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        dut.i_clk.value = 0
        dut.i_rstb.value = 0
        dut.i_enable.value = 0
        dut.i_clear.value = 0
        dut.i_load.value = 0
        dut.i_direction.value = 0
        dut.i_load_value.value = 0
        clock = cocotb.start_soon(Clock(dut.i_clk, self.config.clock_ns, unit="ns").start(start_high=False))
        await CounterSpecSequence(self.config).start(self.env.sequencer)
        clock.cancel()
        self.drop_objection()
