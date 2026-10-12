"""Event-count reference, portable stage assertions, and waveform checks in PyUVM.

Digital simulation checks reset sequencing. It does not model metastability,
technology minimum pulse width, recovery/removal, or CDC/RDC signoff.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
import json
import os
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer
from cocotb.utils import get_sim_time, get_time_from_sim_steps
from pyuvm import (
    ConfigDB, uvm_analysis_export, uvm_analysis_port, uvm_driver, uvm_env,
    uvm_monitor, uvm_scoreboard, uvm_sequencer, uvm_sequence_item,
)

PHASES = ("low", "high", "before_rise", "after_rise", "before_fall", "after_fall", "on_rise", "on_fall")


def picoseconds(variable: str, default: str) -> int:
    value = Decimal(os.getenv(variable, default)) * 1000
    assert value.is_finite() and value == int(value), f"{variable} must be a whole number of ps"
    return int(value)


@dataclass(frozen=True)
class ResetSynchronizerConfig:
    stages: int
    seed: int
    random_cycles: int
    period_ps: int
    near_ps: int
    pulse_ps: int
    check_stages: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> ResetSynchronizerConfig:
        structural = os.getenv("RESET_SYNCHRONIZER_CHECK_STAGES", "1")
        assert structural in ("0", "1")
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/reset_synchronizer/results.xml")).with_name("coverage.json")
        config = cls(
            stages=int(os.getenv("RESET_SYNCHRONIZER_STAGES", "2")),
            seed=int(os.getenv("RESET_SYNCHRONIZER_SEED", "20261011")),
            random_cycles=int(os.getenv("RESET_SYNCHRONIZER_RANDOM_CYCLES", "2000")),
            period_ps=picoseconds("TEST_CLOCK_PERIOD_NS", "4"),
            near_ps=picoseconds("RESET_SYNCHRONIZER_NEAR_NS", "0.01"),
            pulse_ps=picoseconds("RESET_SYNCHRONIZER_PULSE_NS", "0.01"),
            check_stages=structural == "1",
            coverage_file=Path(os.getenv("RESET_SYNCHRONIZER_COVERAGE_FILE", str(report))),
        )
        assert config.stages >= 2 and config.random_cycles >= 1000
        assert config.near_ps >= 3 and config.pulse_ps >= 3
        assert config.period_ps % 2 == 0 and config.period_ps // 2 > 2 * max(config.near_ps, config.pulse_ps)
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Use 1 ps precision or finer"
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "This suite verifies zero-delay RTL; use TEST_SETTLE_NS=0"
        return config


def logic(handle) -> str:
    return str(handle.value).lower()


def reset_negedge(before: str, after: str) -> bool:
    """IEEE four-state edge rules: 1 to 0/X/Z, or X/Z to 0."""
    return before == "1" and after in "0xz" or before in "xz" and after == "0"


class ResetSynchronizerItem(uvm_sequence_item):
    def __init__(self, label, clk, rstb, *, duration_ps, context="running", expected_unknown=None):
        super().__init__(label)
        assert clk in (0, 1) and str(rstb).lower() in "01xz"
        assert duration_ps >= 3 and context in ("running", "stopped")
        self.clk, self.rstb, self.duration_ps = clk, str(rstb).lower(), duration_ps
        self.context, self.expected_unknown = context, expected_unknown


@dataclass(frozen=True)
class Observation:
    time_ps: int
    clk: str
    rstb: str
    output: str
    stages: str | None
    label: str
    item: ResetSynchronizerItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    clk: str
    rstb: str
    allowed: bool
    rising_clock: bool


class ResetSynchronizerDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(3, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            old_clk, old_reset = logic(cocotb.top.i_clk), logic(cocotb.top.i_async_rstb)
            rising = old_clk == "0" and item.clk == 1
            self.active.update(item=item, stage="settled", time_ps=int(get_sim_time(unit="ps")),
                               allowed=rising or reset_negedge(old_reset, item.rstb), rising_clock=rising)
            cocotb.top.i_clk.value = item.clk
            cocotb.top.i_async_rstb.value = item.rstb
            await Timer(1, unit="ps")
            self.active["sample"].set()
            await ReadOnly()
            self.active["allowed"] = False
            # Reserve 1 ps to leave ReadOnly before the next drive. Actual
            # drive-to-drive spacing equals duration_ps, including short pulses.
            await Timer(item.duration_ps - 2, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed held sample"
            self.seq_item_port.item_done()


class ResetSynchronizerMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)
        self.stage_handle = getattr(cocotb.top, "sync_stages", None) if self.config.check_stages else None
        if self.config.check_stages:
            assert self.stage_handle is not None and len(self.stage_handle) == self.config.stages, "Portable sync_stages vector is required"

    async def activity(self, signal, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            allowed, rising = self.active["allowed"], self.active["rising_clock"]
            await ReadOnly()
            value = logic(handle)
            if value != previous:
                self.ap.write(Activity(signal, value, logic(cocotb.top.i_clk), logic(cocotb.top.i_async_rstb), allowed, rising))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.activity("o_rstb", cocotb.top.o_rstb))]
        if self.stage_handle is not None:
            tasks.append(cocotb.start_soon(self.activity("sync_stages", self.stage_handle)))
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    self.active["time_ps"], logic(cocotb.top.i_clk), logic(cocotb.top.i_async_rstb),
                    logic(cocotb.top.o_rstb), logic(self.stage_handle) if self.stage_handle is not None else None,
                    item.get_name(), item, self.active["stage"],
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()


class ResetSynchronizerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.base, self.edges = "0", 0
        self.checks = self.held_checks = self.random_checks = self.unknown_violations = 0
        self.transitions = Counter()
        self.phases, self.contexts, self.reassertions, self.stops, self.pulses = set(), set(), set(), set(), set()
        self.unknowns, self.unknown_sources, self.progress, self.release_counts = set(), set(), set(), set()
        self.last_clock = self.last_reset = None
        self.last_assertion = None
        self.releases = self.asynchronous_assertions = 0

    def expected_stages(self) -> str:
        # Count elapsed qualifying edges rather than duplicating the RTL shift.
        return self.base * (self.config.stages - self.edges) + "1" * self.edges

    def next_state(self, clk, rstb):
        old_clk, old_reset = (self.previous.clk, self.previous.rstb) if self.previous else ("0", "0")
        if rstb == "0":
            return "0", 0
        if old_clk == "0" and clk == "1" or reset_negedge(old_reset, rstb):
            return (self.base, min(self.config.stages, self.edges + 1)) if rstb == "1" else ("x", 0)
        return self.base, self.edges

    def write(self, observation):
        if isinstance(observation, Activity):
            assert observation.allowed, f"Out-of-event activity changed {observation.signal} to {observation.value}"
            base, edges = self.next_state(observation.clk, observation.rstb)
            predicted = base * (self.config.stages - edges) + "1" * edges
            expected = predicted[0] if observation.signal == "o_rstb" else predicted
            assert observation.value == expected, f"Event waveform violated stage latency/clear: {observation.signal}={observation.value}, expected={expected}"
            if observation.rstb == "0":
                assert set(observation.value) <= {"0"}, "Reset assertion did not clear output/stages"
            if observation.signal == "o_rstb" and observation.value == "1":
                assert observation.rstb == "1" and observation.clk == "1" and observation.rising_clock, "Reset released asynchronously or without a rising clock"
            self.transitions[observation.signal] += 1
            return
        config, item = self.config, observation.item
        assert observation.clk == str(item.clk) and observation.rstb == item.rstb, "Clock/reset stimulus was coerced"
        illegal = observation.rstb if observation.rstb in "xz" else None
        try:
            assert illegal is None, f"Unknown-reset assertion failed: i_async_rstb={illegal}"
        except AssertionError:
            if item.expected_unknown != illegal:
                raise
            if observation.stage == "settled":
                if illegal not in self.unknowns:
                    self.logger.info("Expected unknown-reset assertion: i_async_rstb=%s", illegal)
                self.unknowns.add(illegal)
                self.unknown_violations += 1
        else:
            assert item.expected_unknown is None, "Expected unknown reset became known"
        if observation.stage == "held":
            self.held_checks += 1
            self.check_outputs(observation)
            return
        assert observation.stage == "settled"
        previous = self.previous
        old_clk, old_reset = (previous.clk, previous.rstb) if previous else ("0", "0")
        rising = old_clk == "0" and observation.clk == "1"
        falling = old_clk == "1" and observation.clk == "0"
        reset_change = old_reset != observation.rstb
        before_edges = self.edges
        self.base, self.edges = self.next_state(observation.clk, observation.rstb)
        self.check_outputs(observation)
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        if observation.rstb == "1":
            self.progress.add(self.edges)
        if previous and previous.output != "1" and observation.output == "1":
            self.releases += 1
            self.release_counts.add(self.edges)
            assert rising and self.edges == config.stages, "Release skipped synchronization stages"
        kind = "assert" if observation.rstb == "0" else "deassert" if observation.rstb == "1" else None
        if reset_change and kind:
            phase = "high" if observation.clk == "1" else "low"
            self.phases.add((kind, phase))
            self.contexts.add((kind, item.context))
            if rising or falling:
                self.phases.add((kind, "on_rise" if rising else "on_fall"))
            elif self.last_clock and 0 < observation.time_ps - self.last_clock[0] <= config.near_ps:
                self.phases.add((kind, "after_" + self.last_clock[1]))
            self.last_reset = observation.time_ps, kind
            if kind == "assert":
                self.last_assertion = observation.time_ps, observation.clk
                if old_reset == "1":
                    self.reassertions.add((before_edges, observation.clk))
                if not rising and not falling:
                    self.asynchronous_assertions += 1
            elif self.last_assertion:
                duration = observation.time_ps - self.last_assertion[0]
                if duration == config.pulse_ps:
                    self.pulses.add(self.last_assertion[1])
        if rising or falling:
            edge = "rise" if rising else "fall"
            if self.last_reset and 0 < observation.time_ps - self.last_reset[0] <= config.near_ps:
                self.phases.add((self.last_reset[1], "before_" + edge))
            self.last_clock = observation.time_ps, edge
        if item.context == "stopped":
            assert old_clk == observation.clk and item.duration_ps >= 2 * config.period_ps, "Stopped-clock scenario did not stop/hold the clock"
            if observation.rstb == "1" and self.edges < config.stages:
                self.stops.add((self.edges, observation.clk))
        if illegal and reset_change:
            self.unknown_sources.add((old_reset, illegal))
        self.previous = observation

    def check_outputs(self, observation):
        expected = self.expected_stages()
        assert observation.output == expected[0], (
            f"{observation.label}/{observation.stage}: reset={observation.rstb}, edges={self.edges}, "
            f"output={observation.output}, expected={expected[0]}"
        )
        if observation.stages is not None:
            assert observation.stages == expected, f"Stage progression/clear failed: stages={observation.stages}, expected={expected}"
            assert observation.output == observation.stages[0], "Output does not track the final stage"

    def report(self):
        config = self.config
        goals = {
            "assert_deassert_all_clock_phases": set(product(("assert", "deassert"), PHASES)) <= self.phases,
            "running_stopped_reset_transition_cross": set(product(("assert", "deassert"), ("running", "stopped"))) <= self.contexts,
            "reassert_every_release_stage_in_both_phases": set(product(range(config.stages), "01")) <= self.reassertions,
            "stopped_clock_every_pending_stage_in_both_phases": set(product(range(config.stages), "01")) <= self.stops,
            "every_release_progress_count": self.progress == set(range(config.stages + 1)),
            "release_exactly_stages_rising_edges": self.releases > 0 and self.release_counts == {config.stages},
            "asynchronous_assertion_without_clock": self.asynchronous_assertions >= 2,
            "modeled_short_pulse_in_both_clock_phases": self.pulses == {"0", "1"},
            "known_and_asserted_sources_to_x_and_z": set(product("01", "xz")) <= self.unknown_sources,
            "active_unknown_reset_assertions": self.unknowns == {"x", "z"},
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_clock_reset_actions": self.random_checks == config.random_cycles,
        }
        return {
            "status": "PASS" if all(goals.values()) else "FAIL", "parameters": {"STAGES": config.stages},
            "seed": config.seed, "simulator": cocotb.SIM_NAME, "clock_period_ps": config.period_ps,
            "near_edge_offset_ps": config.near_ps, "modeled_pulse_width_ps": config.pulse_ps,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "expected_unknown_violations": self.unknown_violations, "release_events": self.releases,
            "portable_stage_assertions": "PASS" if config.check_stages else "NOT_RUN", "goals": goals,
            "bins": {"reset_transition_phases": sorted(self.phases), "reset_transition_clock_context": sorted(self.contexts),
                     "reassertion_stage_phase": sorted(self.reassertions), "stopped_stage_phase": sorted(self.stops),
                     "release_progress_counts": sorted(self.progress), "release_edge_counts": sorted(self.release_counts),
                     "short_pulse_phases": sorted(self.pulses), "unknown_reset_sources": sorted(self.unknown_sources),
                     "output_stage_transitions": dict(self.transitions)},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing reset synchronizer coverage: {missing}"
        self.logger.info("Reset synchronizer coverage PASS: %d transactions", self.checks)


class ResetSynchronizerEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = ResetSynchronizerDriver("driver", self)
        self.monitor = ResetSynchronizerMonitor("monitor", self)
        self.scoreboard = ResetSynchronizerScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
