"""Directed and seeded clock_gate sequences."""

from itertools import product
import random
from pyuvm import uvm_sequence
from clock_gate.constants import CONTROLS
from clock_gate.transaction import ClockGateItem, ControlChange


class ClockGateSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("clock_gate_sequence")
        self.config = config

    async def cycle(self, label, changes=(), *, unknown=None):
        item = ClockGateItem(label, changes, unknown=unknown)
        await self.start_item(item)
        await self.finish_item(item)

    async def controls(self, label, enable, test_enable=0):
        await self.cycle(label, (ControlChange(1, enable, test_enable),))

    async def body(self):
        half, period = self.config.half_ps, self.config.period_ps
        # The first pulse uses the controls established at time zero, with no reset.
        await self.cycle("startup_first_pulse")
        await self.cycle("startup_second_pulse")
        for enable, override in product((0, 1), repeat=2):
            await self.controls("control_combination", enable, override)
            await self.cycle("control_combination_hold")

        # For each control and polarity, test 1 ps before/after both edges.
        # The other control is low so that every request changes gate behavior.
        offsets = (half - 1, half + 1, period - 1, 1)
        for control, value, offset in product(CONTROLS, (0, 1), offsets):
            baseline = {name: 0 for name in CONTROLS}
            baseline[control] = 1 - value
            await self.controls("near_edge_baseline", **baseline)
            await self.cycle("near_edge_request", (ControlChange(offset, **{control: value}),))
            await self.cycle("near_edge_effect")

        # Low-phase transparency must use the final request before the rise.
        # Short high-phase control pulses must neither create nor truncate gclk.
        for control, enabled in product(CONTROLS, (0, 1)):
            controls = {name: 0 for name in CONTROLS}
            controls[control] = enabled
            await self.controls("transient_baseline", **controls)
            for phase, start in (("low", 0), ("high", half)):
                await self.cycle(f"{phase}_phase_control_transient", (
                    ControlChange(start + half // 4, **{control: 1 - enabled}),
                    ControlChange(start + 3 * half // 4, **{control: enabled}),
                ))

        await self.controls("single_pulse", 1)
        await self.controls("short_disabled", 0)
        await self.cycle("short_disabled")
        await self.controls("multiple_pulses", 1)
        for _ in range(7):
            await self.cycle("multiple_pulses")
        await self.controls("long_disabled", 0)
        for _ in range(63):
            await self.cycle("long_disabled")
        await self.controls("long_enabled", 1)
        for _ in range(63):
            await self.cycle("long_enabled")
        for index in range(16):
            await self.controls("back_to_back", index % 2)

        await self.controls("scan_open", 0, 1)
        for index in range(16):
            await self.cycle("scan_functional_toggle", (
                ControlChange(1, enable=index % 2),
                ControlChange(half + half // 2, enable=1 - index % 2),
            ))
        await self.controls("scan_functional_disable", 0, 1)
        await self.cycle("scan_close_high", (ControlChange(half + half // 2, test_enable=0),))
        await self.cycle("scan_closed_next_pulse")

        rng = random.Random(self.config.seed)
        for index in range(self.config.random_cycles):
            low = rng.choice((1, half // 2, half - 1))
            high = rng.choice((half + 1, half + half // 2, period - 1))
            await self.cycle(f"random_{index}", (
                ControlChange(low, rng.randrange(2), rng.randrange(2)),
                ControlChange(high, rng.randrange(2), rng.randrange(2)),
            ))

        # Unknowns are illegal even when a known one masks them in the OR.
        # Hold each injection through a falling edge and the next full pulse.
        for control, unknown, other, phase in product(CONTROLS, ("x", "z"), (0, 1), ("low", "high")):
            baseline = {name: other for name in CONTROLS}
            baseline[control] = 0
            await self.controls("unknown_baseline", **baseline)
            offset = half // 2 if phase == "low" else half + half // 2
            await self.cycle(f"unknown_{control}_{unknown}_{other}_{phase}", (
                ControlChange(offset, **{control: unknown}),
            ), unknown=(control, unknown))
            await self.cycle("unknown_held", unknown=(control, unknown))
            await self.controls("unknown_recovery", 0)
        await self.controls("final_disabled", 0)
        await self.cycle("final_complete_low_phase")
