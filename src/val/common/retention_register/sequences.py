"""Directed and seeded retention_register sequences."""

from itertools import product
import os
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from retention_register.model import violations
from retention_register.transaction import Inputs, RetentionItem


class RetentionSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("retention_sequence")
        self.config = config
        self.valid_save = False
        self.previous_command = None

    async def send(self, label, inputs, *, expected=(), duration_ps=None, context="running"):
        item = RetentionItem(label, inputs, duration_ps=duration_ps or self.config.period_ps // 4, expected=expected, context=context)
        await self.start_item(item)
        await self.finish_item(item)

    async def cycle(self, label, data, *, rstb=1, enable=1, save=0, restore=0, negative=False):
        inputs = Inputs(1, rstb, enable, save, restore, data)
        expected = violations(self.config, inputs, self.valid_save, self.previous_command) if negative else set()
        await self.send(label + "_setup", Inputs(0, rstb, enable, save, restore, data), expected=expected)
        await self.send(label + "_rise", inputs, expected=expected)
        # Exercise ignored activity in the high phase and at a falling edge.
        alternate = bits(data, self.config.width).translate(str.maketrans("01xz", "10zx"))
        activity = Inputs(1, rstb, 1 - enable if enable in (0, 1) else 0,
                          1 - save if save in (0, 1) else 0, 1 - restore if restore in (0, 1) else 0, alternate)
        await self.send(label + "_high_activity", activity, expected=expected)
        await self.send(label + "_fall", Inputs(0, activity.rstb, activity.enable, activity.save, activity.restore, activity.data), expected=expected)
        if str(rstb) != "1":
            self.valid_save, self.previous_command = False, "reset" if str(rstb) == "0" else "unknown"
        elif str(save) in "xz" or str(restore) in "xz":
            self.valid_save, self.previous_command = False, "unknown"
        elif restore == 1:
            self.valid_save, self.previous_command = False, "restore"
        elif save == 1:
            self.valid_save, self.previous_command = True, "save"
        else:
            self.previous_command = "unknown" if self.config.has_enable and str(enable) in "xz" else "capture" if not self.config.has_enable or enable == 1 else "hold"

    async def initialize(self):
        await self.cycle("cold_reset", self.config.maximum, rstb=0, enable=0)
        await self.send("reset_release_low", Inputs(0, 1, 0, 0, 0, 0))

    async def epoch(self, data, *, label="pattern", long=False):
        config = self.config
        changed = bits(data, config.width).translate(str.maketrans("01xz", "10zx"))
        await self.cycle(label + "_load", data)
        await self.cycle(label + "_save", changed, enable=0, save=1)
        await self.cycle(label + "_overwrite_a", changed)
        await self.cycle(label + "_overwrite_b", config.reset_value)
        if long:
            # Both levels are held with no clock edge. This is a stopped-clock
            # logical interval, not a main-supply-off simulation.
            for phase in (0, 1):
                await self.send("stop_phase_setup", Inputs(phase, 1, 0, 0, 0, changed))
                await self.send("retained_clock_stop", Inputs(phase, 1, 0, 0, 0, data),
                                context="stopped", duration_ps=8 * config.period_ps)
        await self.cycle(label + "_restore", changed, enable=0, restore=1)
        await self.cycle(label + "_post_restore_write", changed)

    async def probe(self, name):
        config = self.config
        await self.initialize()
        if name not in ("restore_without_save", "unknown_reset_x", "unknown_reset_z"):
            await self.cycle("probe_load", config.maximum)
            await self.cycle("probe_save", 0, enable=0, save=1)
            await self.cycle("probe_modify", 0)
        values = dict(rstb=1, enable=0, save=0, restore=0)
        if name.startswith("unknown_"):
            field, state = name.removeprefix("unknown_").rsplit("_", 1)
            values["rstb" if field == "reset" else field] = state
        elif name == "save_restore_conflict":
            values.update(save=1, restore=1)
        elif name == "enable_save":
            values.update(save=1, enable=1)
        elif name == "enable_restore":
            values.update(restore=1, enable=1)
        elif name == "restore_without_save":
            values.update(restore=1)
        elif name == "repeat_save":
            await self.cycle("first_repeated_save", 0, enable=0, save=1)
            values.update(save=1)
        elif name == "repeat_restore":
            await self.cycle("first_repeated_restore", 0, enable=0, restore=1)
            values.update(restore=1)
        else:
            raise AssertionError(f"Unknown protocol probe {name}")
        await self.cycle("unexpected_protocol_violation", config.maximum, **values)

    async def body(self):
        config = self.config
        probe = os.getenv("RETENTION_REGISTER_PROTOCOL_PROBE", "")
        if probe:
            await self.probe(probe)
            return
        await self.initialize()
        # Front-load an unknown save to expose silent control interpretation.
        await self.cycle("unknown_save_preload", config.maximum)
        await self.cycle("unknown_save", 0, enable=0, save="x", negative=True)
        await self.initialize()
        for word in config.patterns:
            await self.epoch(word)
        rng = random.Random(config.seed)
        for long in (False, True):
            for word in (0, config.maximum, int(("01" * config.width)[:config.width], 2), int(("10" * config.width)[:config.width], 2)):
                await self.epoch(word, long=long)
            await self.epoch(rng.getrandbits(config.width), label="random_saved", long=long)
        for index in range(16):
            await self.epoch(config.maximum if index % 2 else 0, label="repeated_epoch")
        # Two separate saves with an intervening write: only the newest wins.
        await self.cycle("latest_load_a", 0)
        await self.cycle("latest_save_a", config.maximum, enable=0, save=1)
        await self.cycle("latest_load_b", config.maximum)
        await self.cycle("latest_save_b", 0, enable=0, save=1)
        await self.cycle("latest_overwrite", 0)
        await self.cycle("latest_restore", 0, enable=0, restore=1)

        for reset, restore, save, enable in product((0, 1), repeat=4):
            await self.initialize()
            await self.cycle("priority_load", config.maximum)
            await self.cycle("priority_save", 0, enable=0, save=1)
            await self.cycle("priority_modify", 0)
            # Restore must select the saved all-one word, even when input data
            # differs and functional enable is illegally active.
            candidate_data = 0 if restore else config.maximum
            await self.cycle("priority_combination", candidate_data, rstb=reset, restore=restore, save=save, enable=enable, negative=True)
        for field, unknown in product(("rstb", "enable", "save", "restore"), ("x", "z")):
            await self.initialize()
            await self.cycle("unknown_load", config.maximum)
            await self.cycle("unknown_known_save", 0, enable=0, save=1)
            values = dict(rstb=1, enable=0, save=0, restore=0)
            values[field] = unknown
            await self.cycle("sample_unknown_control", 0, **values, negative=True)
            if field != "rstb":
                await self.cycle("reset_masks_unknown_control", 0, **{**values, "rstb": 0}, negative=True)
        await self.initialize()
        await self.cycle("illegal_restore_without_save", config.maximum, restore=1, enable=0, negative=True)
        await self.cycle("prepare_repeat_save", 0)
        await self.cycle("first_save", 0, enable=0, save=1)
        await self.cycle("illegal_repeat_save", config.maximum, enable=0, save=1, negative=True)
        await self.cycle("first_restore", 0, enable=0, restore=1)
        await self.cycle("illegal_repeat_restore", config.maximum, enable=0, restore=1, negative=True)
        for phase in (0, 1):
            await self.cycle("offedge_reset_load", config.maximum ^ config.reset_value)
            await self.send("reset_phase_setup", Inputs(phase, 1, 0, 0, 0, 0))
            await self.send("offedge_reset_assert", Inputs(phase, 0, 0, 0, 0, config.maximum))
            await self.cycle("sample_reset", 0, rstb=0, enable=0)
            await self.send("release_phase_setup", Inputs(phase, 0, 0, 0, 0, 0))
            await self.send("offedge_reset_release", Inputs(phase, 1, 0, 0, 0, 0))
        for index in range(32):
            await self.cycle("hold_stress", rng.getrandbits(config.width), enable=0)
        for index in range(config.random_cycles):
            word = "".join(rng.choice("01xz") for _ in range(config.width)) if index % 7 == 0 else rng.getrandbits(config.width)
            operation = rng.choice(("capture", "capture", "hold", "save", "restore", "reset"))
            if operation == "save" and self.previous_command == "save":
                operation = "capture"
            if operation == "restore" and not self.valid_save:
                operation = "capture"
            await self.cycle(f"random_cycle_{index}", word, rstb=0 if operation == "reset" else 1,
                             enable=1 if operation == "capture" else 0, save=int(operation == "save"), restore=int(operation == "restore"))
        await self.initialize()
