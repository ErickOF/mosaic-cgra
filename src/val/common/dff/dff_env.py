"""PyUVM components and an independent, port-only DFF reference model."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
import json
import os
from pathlib import Path

import cocotb
from cocotb.triggers import First, ReadOnly, Timer
from cocotb.utils import get_sim_time, get_time_from_sim_steps
from pyuvm import (
    ConfigDB, uvm_analysis_export, uvm_analysis_port, uvm_driver, uvm_env,
    uvm_monitor, uvm_scoreboard, uvm_sequencer, uvm_sequence_item,
)


@dataclass(frozen=True)
class DffConfig:
    width: int
    reset_value: int
    async_reset: bool
    has_enable: bool
    seed: int
    random_cycles: int
    period_ps: int
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> DffConfig:
        period = Decimal(os.getenv("TEST_CLOCK_PERIOD_NS", "4")) * 1000
        assert period.is_finite() and period == int(period)
        assert period >= 32 and int(period) % 4 == 0, "Use a clock period divisible by 4 ps and at least 32 ps"
        async_reset = os.getenv("DFF_ASYNC_RESET", "0")
        has_enable = os.getenv("DFF_HAS_ENABLE", "1")
        assert async_reset in ("0", "1") and has_enable in ("0", "1")
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/dff/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("DFF_WIDTH", str(len(cocotb.top.o_q)))),
            reset_value=int(os.getenv("DFF_RESET_VALUE", "0"), 0),
            async_reset=async_reset == "1", has_enable=has_enable == "1",
            seed=int(os.getenv("DFF_SEED", "20261010")),
            random_cycles=int(os.getenv("DFF_RANDOM_CYCLES", "2000")),
            period_ps=int(period),
            coverage_file=Path(os.getenv("DFF_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.width >= 1 and 0 <= config.reset_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 randomized cycles"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Waveform checking requires 1 ps precision or finer"
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "This suite checks zero-delay RTL; use TEST_SETTLE_NS=0"
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def reset_bits(self) -> str:
        return f"{self.reset_value:0{self.width}b}"

    @property
    def step_ps(self) -> int:
        return self.period_ps // 4


@dataclass(frozen=True)
class Inputs:
    clk: int
    rstb: int | str
    enable: int | str
    data: int | str

    def data_bits(self, width: int) -> str:
        if isinstance(self.data, int):
            assert 0 <= self.data < 1 << width, "Do not truncate stimulus data"
            return f"{self.data:0{width}b}"
        assert len(self.data) == width and set(self.data.lower()) <= set("01xz")
        return self.data.lower()


class DffItem(uvm_sequence_item):
    """One clock phase or off-edge control change, with optional illegal control."""

    def __init__(self, label, inputs, *, unknown=None):
        super().__init__(label)
        self.inputs = inputs
        self.unknown = unknown


@dataclass(frozen=True)
class Snapshot:
    time_ps: int
    clk: str
    rstb: str
    enable: str
    data: str
    q: str
    label: str
    expected_unknown: tuple[str, str] | None
    requested: Inputs | None


@dataclass(frozen=True)
class OutputChange:
    time_ps: int
    before: str
    after: str


def logic(signal) -> str:
    """Keep all four logic states visible to the model and control assertions."""
    return str(signal.value).lower()


def illegal_control(rstb: str, enable: str, has_enable: bool) -> tuple[str, str] | None:
    """Reset must be known; enable must be known only when it is relevant."""
    if rstb not in ("0", "1"):
        return "rstb", rstb
    if rstb == "1" and has_enable and enable not in ("0", "1"):
        return "enable", enable
    return None


class DffDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            self.active["item"] = item
            self.dut.i_clk.value = item.inputs.clk
            self.dut.i_rstb.value = item.inputs.rstb
            self.dut.i_enable.value = item.inputs.enable
            self.dut.i_d.value = item.inputs.data_bits(self.config.width)
            await Timer(self.config.step_ps - 2, unit="ps")
            # Sample even identical transactions, which have no input callback.
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "The monitor did not consume the sample"
            self.seq_item_port.item_done()


class DffMonitor(uvm_monitor):
    """Observe settled ports and every output transition, including short glitches."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    def snapshot(self) -> Snapshot:
        item = self.active["item"]
        return Snapshot(
            int(get_sim_time(unit="ps")), logic(self.dut.i_clk), logic(self.dut.i_rstb),
            logic(self.dut.i_enable), logic(self.dut.i_d), logic(self.dut.o_q),
            item.get_name() if item else "startup", item.unknown if item else None,
            item.inputs if item else None,
        )

    async def output_changes(self):
        previous = logic(self.dut.o_q)
        while True:
            await self.dut.o_q.value_change
            current = logic(self.dut.o_q)
            # Re-arm immediately: ReadOnly here could hide a transient output.
            self.ap.write(OutputChange(int(get_sim_time(unit="ps")), previous, current))
            previous = current

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        self.ap.write(self.snapshot())
        output_task = cocotb.start_soon(self.output_changes())
        try:
            while True:
                await First(
                    self.dut.i_clk.value_change, self.dut.i_rstb.value_change,
                    self.dut.i_enable.value_change, self.dut.i_d.value_change,
                    self.active["sample"].wait(),
                )
                await ReadOnly()
                self.ap.write(self.snapshot())
                self.active["sample"].clear()
        finally:
            output_task.cancel()


class DffScoreboard(uvm_scoreboard):
    """Model only specified clock/reset events; audit the entire output waveform."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.state = None  # The spec does not define an unreset power-up value.
        self.ignore_start = 0
        self.ignored_intervals = []
        self.expected_changes = []
        self.output_changes = []
        self.commands = Counter()
        self.checks = self.random_checks = 0
        self.reset_enable = set()
        self.reset_release = set()
        self.data_activity = set()
        self.enable_transitions = set()
        self.bit_values = set()
        self.unknown_controls = set()
        self.ignored_enable = set()
        self.masked_unknown_enable = set()
        self.short_reset_phases = set()
        self.pending_reset = None
        self.run_command = None
        self.command_pairs = set()
        self.run_length = 0
        self.longest_runs = Counter()

    def write(self, observation):
        if isinstance(observation, OutputChange):
            self.output_changes.append(observation)
            return
        assert isinstance(observation, Snapshot)
        config, previous = self.config, self.previous
        self.checks += 1
        assert observation.clk in ("0", "1"), "The functional clock must be known"
        if observation.requested:
            requested = observation.requested
            assert (observation.clk, observation.rstb, observation.enable, observation.data) == (
                str(requested.clk), str(requested.rstb).lower(), str(requested.enable).lower(),
                requested.data_bits(config.width),
            ), "Stimulus did not reach the DUT without four-state coercion"
        rising = previous is not None and previous.clk == "0" and observation.clk == "1"
        reset_assert = previous is not None and previous.rstb != "0" and observation.rstb == "0"
        reset_release = previous is not None and previous.rstb == "0" and observation.rstb == "1"
        before, command = self.state, None
        if config.async_reset and observation.rstb not in ("0", "1"):
            # An illegal asynchronous reset has no specified numeric behavior.
            self.state = None
        if rising:
            violation = illegal_control(observation.rstb, observation.enable, config.has_enable)
            assert violation == observation.expected_unknown, (
                f"{observation.label}: known-control assertion {violation}, "
                f"expected {observation.expected_unknown}"
            )
            if violation:
                name, value = violation
                self.unknown_controls.add((name, value, observation.enable if name == "rstb" else "1"))
                self.logger.info("Expected known-control assertion: %s=%s", name, value)
                self.state = None
            elif observation.rstb == "0":
                self.state, command = config.reset_bits, "reset"
                self.reset_enable.add(observation.enable)
                if observation.enable in ("x", "z"):
                    self.masked_unknown_enable.add(observation.enable)
            elif not config.has_enable or observation.enable == "1":
                self.state, command = observation.data, "capture"
                if not config.has_enable:
                    self.ignored_enable.add(observation.enable)
            else:
                command = "hold"
            self.commands[command or "illegal"] += 1
            self.random_checks += observation.label.startswith("random_")
            if self.run_command and command:
                self.command_pairs.add((self.run_command, command))
            if command == self.run_command:
                self.run_length += 1
            else:
                self.run_command, self.run_length = command, 1
            if command:
                self.longest_runs[command] = max(self.longest_runs[command], self.run_length)
            if self.pending_reset:
                self.pending_reset["clocked"] = True
        if reset_assert:
            phase = "low" if observation.clk == "0" else "high"
            self.pending_reset = {"phase": phase, "clocked": rising, "before": before}
            if config.async_reset:
                self.state = config.reset_bits
                self.commands["async_assert"] += 1
        if reset_release:
            self.reset_release.add(observation.clk)
            if self.pending_reset and not self.pending_reset["clocked"]:
                # A discriminating reset pulse starts with non-reset state.
                if self.pending_reset["before"] not in (None, config.reset_bits):
                    self.short_reset_phases.add(self.pending_reset["phase"])
            self.pending_reset = None
        if previous:
            phase = "low" if observation.clk == "0" else "high"
            if previous.data != observation.data and observation.rstb == "1" and not rising:
                self.data_activity.add((phase, observation.enable))
            if previous.enable != observation.enable and observation.enable in ("0", "1"):
                self.enable_transitions.add((phase, observation.enable))
        if before is None and self.state is not None:
            self.ignored_intervals.append((self.ignore_start, observation.time_ps))
            self.ignore_start = None
        elif before is not None and self.state is None:
            self.ignore_start = observation.time_ps
        elif before is not None and self.state != before:
            self.expected_changes.append((observation.time_ps, before, self.state))
        if self.state is not None:
            assert observation.q == self.state, (
                f"{observation.label} at {observation.time_ps} ps: o_q={observation.q}, "
                f"expected {self.state}; clk={observation.clk}, rstb={observation.rstb}, "
                f"enable={observation.enable}, data={observation.data}"
            )
            for bit, value in enumerate(reversed(self.state)):
                if value in ("0", "1"):
                    self.bit_values.add((bit, value))
        self.previous = observation

    def report(self):
        config = self.config
        expected_unknowns = set(product(("rstb",), ("x", "z"), ("0", "1")))
        if config.has_enable:
            expected_unknowns |= set(product(("enable",), ("x", "z"), ("1",)))
        intervals = self.ignored_intervals + ([(self.ignore_start, float("inf"))] if self.ignore_start is not None else [])
        actual = [
            (change.time_ps, change.before, change.after) for change in self.output_changes
            if not any(start <= change.time_ps <= end for start, end in intervals)
        ]
        goals = {
            "reset_while_enabled_and_disabled": {"0", "1"} <= self.reset_enable,
            "reset_release_before_rising_edge": "0" in self.reset_release,
            "short_reset_pulses_in_both_phases": self.short_reset_phases == {"low", "high"},
            "capture": self.commands["capture"] > 0,
            "consecutive_captures": self.longest_runs["capture"] >= 16,
            "every_bit_zero_and_one": set(product(range(config.width), ("0", "1"))) <= self.bit_values,
            "data_changes_in_both_phases": set(product(("low", "high"), ("0", "1"))) <= self.data_activity,
            "enable_transitions_in_both_phases": set(product(("low", "high"), ("0", "1"))) <= self.enable_transitions,
            "known_control_assertions": expected_unknowns <= self.unknown_controls,
            "reset_masks_unknown_enable": self.masked_unknown_enable == {"x", "z"},
            "random_cycles": self.random_checks == config.random_cycles,
            "complete_output_waveform": actual == self.expected_changes,
            "final_state_known": self.state is not None and set(self.state) <= {"0", "1"},
        }
        if config.has_enable:
            goals["consecutive_holds"] = self.longest_runs["hold"] >= 16
            goals["alternating_capture_and_hold"] = {("capture", "hold"), ("hold", "capture")} <= self.command_pairs
        else:
            goals["ignored_enable_all_four_states"] = self.ignored_enable == {"0", "1", "x", "z"}
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "RESET_VALUE": config.reset_value,
                           "ASYNC_RESET": int(config.async_reset), "HAS_ENABLE": int(config.has_enable)},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_snapshots": self.checks, "clocked_checks": sum(self.commands.values()) - self.commands["async_assert"],
            "random_cycles": self.random_checks, "output_transitions": len(actual),
            "expected_control_violations": len(self.unknown_controls),
            "commands": dict(self.commands), "longest_runs": dict(self.longest_runs),
            "goals": goals, "bit_value_coverage_percent": 100 * len(self.bit_values) / (2 * config.width),
            "bins": {"reset_enable": sorted(self.reset_enable), "reset_release_clock": sorted(self.reset_release),
                     "short_reset_phases": sorted(self.short_reset_phases), "data_activity": sorted(self.data_activity),
                     "command_pairs": sorted(self.command_pairs),
                     "enable_transitions": sorted(self.enable_transitions), "bit_values": sorted(self.bit_values),
                     "unknown_controls": sorted(self.unknown_controls), "ignored_enable": sorted(self.ignored_enable)},
            "waveform_mismatch": None if actual == self.expected_changes else {
                "expected": self.expected_changes, "actual": actual,
            },
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing DFF coverage or failed assertions: {missing}"
        self.logger.info("DFF coverage PASS: %d clocked checks, %d output transitions",
                         report["clocked_checks"], report["output_transitions"])


class DffEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = DffDriver("driver", self)
        self.monitor = DffMonitor("monitor", self)
        self.scoreboard = DffScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
