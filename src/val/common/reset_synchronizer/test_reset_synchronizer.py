"""Directed reset phases, stopped clocks, interrupted release, and random actions."""

from __future__ import annotations

from itertools import product
import os
import random

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from reset_synchronizer_env import PHASES, ResetSynchronizerConfig, ResetSynchronizerEnv, ResetSynchronizerItem


class ResetSynchronizerSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("reset_synchronizer_sequence")
        self.config = config

    async def send(self, label, clk, rstb, *, duration_ps=None, context="running", expect_unknown=True):
        item = ResetSynchronizerItem(
            label, clk, rstb, duration_ps=duration_ps or self.config.period_ps // 2,
            context=context, expected_unknown=str(rstb) if expect_unknown and rstb in ("x", "z") else None,
        )
        await self.start_item(item)
        await self.finish_item(item)

    async def cycles(self, count, *, rstb=1, label="release"):
        for index in range(count):
            await self.send(f"{label}_{index}_low", 0, rstb)
            await self.send(f"{label}_{index}_rise", 1, rstb)

    async def released(self):
        await self.send("fresh_assert", 0, 0)
        await self.send("fresh_deassert", 0, 1)
        await self.cycles(self.config.stages)

    async def transition_phase(self, kind, phase):
        if kind == "assert":
            await self.released()
        else:
            await self.send("prepare_asserted", 0, 0)
        old, new = (1, 0) if kind == "assert" else (0, 1)
        near = self.config.near_ps
        if phase in ("low", "high"):
            clk = int(phase == "high")
            await self.send("phase_setup", clk, old)
            await self.send(f"{kind}_{phase}", clk, new)
        elif phase.startswith("before_"):
            before = int(phase.endswith("fall"))
            await self.send("before_edge_setup", before, old)
            await self.send(f"{kind}_{phase}", before, new, duration_ps=near)
            await self.send("following_edge", 1 - before, new)
        elif phase.startswith("after_"):
            after = int(phase.endswith("rise"))
            await self.send("after_edge_setup", 1 - after, old)
            await self.send("preceding_edge", after, old, duration_ps=near)
            await self.send(f"{kind}_{phase}", after, new)
        else:
            after = int(phase.endswith("rise"))
            await self.send("simultaneous_setup", 1 - after, old)
            await self.send(f"{kind}_{phase}", after, new)
        await self.cycles(self.config.stages + 1, rstb=new, label="phase_followup")

    async def body(self):
        config = self.config
        probe = os.getenv("RESET_SYNCHRONIZER_UNKNOWN_PROBE", "")
        if probe:
            assert probe in ("x", "z")
            await self.send("unexpected_unknown_reset", 1, probe, expect_unknown=False)
            return
        for kind, phase in product(("assert", "deassert"), PHASES):
            await self.transition_phase(kind, phase)
        for phase in (0, 1):
            await self.released()
            await self.send("stopped_clock_setup", phase, 1)
            await self.send("stopped_assertion", phase, 0, context="stopped", duration_ps=2 * config.period_ps)
            await self.send("stopped_deassertion", phase, 1, context="stopped", duration_ps=2 * config.period_ps)
            await self.cycles(config.stages, label="clock_restart")
            await self.send("released_clock_stop_setup", phase, 1)
            await self.send("stopped_after_release", phase, 1, context="stopped", duration_ps=2 * config.period_ps)
            await self.send("short_pulse_assert", phase, 0, duration_ps=config.pulse_ps)
            await self.send("short_pulse_deassert", phase, 1, context="stopped", duration_ps=2 * config.period_ps)
            await self.cycles(config.stages, label="short_pulse_recovery")

        for count, phase in product(range(config.stages), (0, 1)):
            await self.send("interrupt_reset", phase, 0)
            await self.send("interrupt_deassert", phase, 1)
            await self.cycles(count, label="partial_release")
            await self.send("reassert_phase_setup", phase, 1)
            await self.send("reassert_partial_release", phase, 0)
            await self.send("restart_release", phase, 1)
            await self.cycles(config.stages, label="fresh_chain_after_interrupt")

            await self.send("stop_reset", phase, 0)
            await self.send("stop_deassert", phase, 1)
            await self.cycles(count, label="release_before_stop")
            await self.send("stop_phase_setup", phase, 1)
            await self.send("stopped_pending", phase, 1, context="stopped", duration_ps=2 * config.period_ps)
            await self.cycles(config.stages - count, label="restart_pending_release")

        # Test both negedge-triggering 1->X/Z and non-triggering 0->X/Z.
        # Clock pulses with an unknown reset must never produce known release.
        for source, unknown, phase in product((1, 0), ("x", "z"), (0, 1)):
            if source:
                await self.released()
            await self.send("unknown_source_setup", phase, source)
            await self.send("unknown_reset", phase, unknown)
            await self.cycles(config.stages + 2, rstb=unknown, label="unknown_clock_pulses")
            await self.send("unknown_to_known_release", 0, 1)
            await self.cycles(config.stages, label="unknown_flush")
            await self.send("recover_known_assertion", 0, 0)

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            reset = rng.choice((0, 1, 1, 1, 1, 1, 1, 1, "x", "z"))
            duration = rng.randint(max(config.near_ps, config.pulse_ps), 2 * config.period_ps)
            await self.send(f"random_{index}", rng.randrange(2), reset, duration_ps=duration)
        await self.released()
        await self.send("final_released_hold", 1, 1, context="stopped", duration_ps=2 * config.period_ps)


@test(timeout_time=1, timeout_unit="ms")
class ResetSynchronizerTest(uvm_test):
    def build_phase(self):
        self.config = ResetSynchronizerConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_clk) == len(cocotb.top.i_async_rstb) == len(cocotb.top.o_rstb) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "allowed": False, "rising_clock": False, "sample": Event()})
        self.env = ResetSynchronizerEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        cocotb.top.i_async_rstb.value = 0
        await ResetSynchronizerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
