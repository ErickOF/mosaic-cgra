"""Directed and seeded isolation_cell sequences."""

from itertools import product
import random
from pyuvm import uvm_sequence
from isolation_cell.transaction import Inputs, IsolationCellItem
from mosaic_uvm.logic import bits


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
