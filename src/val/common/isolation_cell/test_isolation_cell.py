"""Specification-driven isolation stimulus with exhaustive small truth tables."""

from __future__ import annotations

from itertools import product
import random

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from isolation_cell_env import IsolationCellConfig, IsolationCellEnv, IsolationCellItem, Inputs


class IsolationCellSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("isolation_cell_sequence")
        self.config = config

    async def send(self, label, data, control):
        unknown = control if isinstance(control, str) and control in ("x", "z") else None
        item = IsolationCellItem(label, Inputs(control, data), unknown=unknown)
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        config = self.config
        active, inactive = config.active_control, config.inactive_control
        invert = str.maketrans("01xz", "10zx")
        for data in config.directed_patterns:
            await self.send("inactive_pattern", data, inactive)
            await self.send("assert_isolation", data, active)
            await self.send("isolated_activity", data.translate(invert), active)
            await self.send("isolated_return", data, active)
            await self.send("release_isolation", data, inactive)
            await self.send("inactive_activity", data.translate(invert), inactive)

        # Illegal controls must raise the known-control diagnostic AND preserve
        # the specification's conservative, per-bit conditional merge behavior.
        for data, control in product(config.directed_patterns, ("x", "z")):
            await self.send("unknown_control", data, control)
            await self.send("recover_known_control", data, inactive)
        if config.width <= 4:
            for bits in product("01xz", repeat=config.width):
                for control in (0, 1, "x", "z"):
                    await self.send("exhaustive_four_state", "".join(bits), control)

        # Logical source-corruption stress illustrates the isolation contract.
        # No supplies or UPF states exist in this portable RTL simulation.
        for index in range(8):
            valid = config.maximum if index % 2 else 0
            await self.send("logical_source_valid", valid, inactive)
            await self.send("logical_assert_before_corruption", valid, active)
            await self.send("logical_source_corrupt_x", "x" * config.width, active)
            await self.send("logical_source_corrupt_z", "z" * config.width, active)
            await self.send("logical_source_restored", valid, active)
            await self.send("logical_release_after_restore", valid, inactive)
        for index in range(64):
            await self.send("long_isolated", ("x" if index % 2 else "z") * config.width, active)
        for index in range(64):
            await self.send("long_pass_through", config.maximum if index % 2 else 0, inactive)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            control = rng.choice((0, 0, 0, 1, 1, 1, "x", "z"))
            data = f"{rng.getrandbits(config.width):0{config.width}b}"
            if rng.randrange(8) == 0:
                bit = rng.randrange(config.width)
                data = data[:bit] + rng.choice(("x", "z")) + data[bit + 1:]
            await self.send(f"random_{index}", data, control)
        await self.send("final_clamp", "x" * config.width, active)
        await self.send("final_isolated_activity", "z" * config.width, active)


@test(timeout_time=1, timeout_unit="ms")
class IsolationCellTest(uvm_test):
    def build_phase(self):
        self.config = IsolationCellConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == len(cocotb.top.o_data) == self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "quiet": False, "sample": Event()})
        self.env = IsolationCellEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_isolate.value = self.config.inactive_control
        cocotb.top.i_data.value = 0
        await IsolationCellSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
