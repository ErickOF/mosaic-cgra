"""Passive waveform checking for the portable MOSAIC clock gate interface."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from decimal import Decimal
from itertools import product, zip_longest
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

CONTROLS = ("enable", "test_enable")


@dataclass(frozen=True)
class ClockGateConfig:
    """Integer picoseconds avoid rounding stimulus onto a clock edge."""

    startup_enabled: bool
    seed: int
    random_cycles: int
    period_ps: int
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> ClockGateConfig:
        period = Decimal(os.getenv("TEST_CLOCK_PERIOD_NS", "4")) * 1000
        assert period.is_finite() and period == int(period)
        assert int(period) >= 16 and int(period) % 2 == 0, (
            "Use an even clock period of at least 16 ps"
        )
        startup = os.getenv("CLOCK_GATE_STARTUP_ENABLED", "0")
        assert startup in ("0", "1")
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/clock_gate/results.xml")).with_name("coverage.json")
        config = cls(
            startup_enabled=startup == "1",
            seed=int(os.getenv("CLOCK_GATE_SEED", "20261010")),
            random_cycles=int(os.getenv("CLOCK_GATE_RANDOM_CYCLES", "2000")),
            period_ps=int(period),
            coverage_file=Path(os.getenv("CLOCK_GATE_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.random_cycles >= 1000, "Use at least 1000 randomized cycles"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, (
            "The edge checks require simulator precision of 1 ps or finer"
        )
        return config

    @property
    def half_ps(self) -> int:
        return self.period_ps // 2


@dataclass(frozen=True)
class ControlChange:
    offset_ps: int
    enable: int | str | None = None
    test_enable: int | str | None = None


class ClockGateItem(uvm_sequence_item):
    """One complete low/high source-clock cycle, with timed control changes."""

    def __init__(self, label, changes=(), *, unknown=None):
        super().__init__(label)
        self.changes = changes
        self.unknown = unknown


@dataclass(frozen=True)
class Snapshot:
    time_ps: int
    clk: str
    enable: str
    test_enable: str
    gclk: str
    label: str
    expected_unknown: tuple[str, str] | None


@dataclass(frozen=True)
class OutputChange:
    time_ps: int
    previous: str
    current: str
    source_level: str


def logic(signal) -> str:
    """Keep X and Z visible instead of coercing an illegal control to bool."""
    return str(signal.value).lower()


def effective_enable(enable: str, test_enable: str) -> str:
    """Four-state OR: a known override masks X/Z, but the diagnostic remains."""
    if "1" in (enable, test_enable):
        return "1"
    return "0" if enable == test_enable == "0" else "x"


class ClockGateDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        # Give the passive monitor time to observe the defined startup low phase.
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active["item"] = item
            events = [(self.config.half_ps, "clock", 1), (self.config.period_ps, "clock", 0)]
            events.extend((change.offset_ps, "controls", change) for change in item.changes)
            previous = 0
            for offset, kind, value in sorted(events, key=lambda event: event[0]):
                assert previous < offset <= self.config.period_ps, (
                    "Stimulus must not coincide with a source-clock edge"
                )
                await Timer(offset - previous, unit="ps")
                previous = offset
                if kind == "clock":
                    self.dut.i_clk.value = value
                else:
                    for name in CONTROLS:
                        control = getattr(value, name)
                        if control is not None:
                            getattr(self.dut, f"i_{name}").value = control
            await ReadOnly()
            self.seq_item_port.item_done()


class ClockGateMonitor(uvm_monitor):
    """Check settled inputs and capture every observable output transition."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    def snapshot(self, item) -> Snapshot:
        return Snapshot(
            int(get_sim_time(unit="ps")), logic(self.dut.i_clk),
            logic(self.dut.i_enable), logic(self.dut.i_test_enable),
            logic(self.dut.o_gclk), item.get_name() if item else "startup",
            item.unknown if item else None,
        )

    async def output_changes(self):
        previous = logic(self.dut.o_gclk)
        while True:
            await self.dut.o_gclk.value_change
            current = logic(self.dut.o_gclk)
            # Do not wait for ReadOnly here: doing so would miss a transient
            # that returns to its original value within the same time step.
            self.ap.write(OutputChange(
                int(get_sim_time(unit="ps")), previous, current,
                logic(self.dut.i_clk),
            ))
            previous = current

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        self.ap.write(self.snapshot(None))
        output_task = cocotb.start_soon(self.output_changes())
        try:
            while True:
                await First(
                    self.dut.i_clk.value_change, self.dut.i_enable.value_change,
                    self.dut.i_test_enable.value_change,
                )
                item = self.active["item"]
                await ReadOnly()
                self.ap.write(self.snapshot(item))
        finally:
            output_task.cancel()


class ClockGateScoreboard(uvm_scoreboard):
    """Derive the latch from ports only; never read an RTL internal node."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.latched = str(int(self.config.startup_enabled))
        self.expected_output = "0"
        self.expected_changes = []
        self.output_changes = []
        self.source_edges = []
        self.requests = []
        self.decisions = []
        self.combinations = set()
        self.unknown_controls = set()
        self.half_cycle_transitions = set()
        self.snapshots = 0

    def write(self, observation):
        if isinstance(observation, OutputChange):
            self.output_changes.append(observation)
            return
        assert isinstance(observation, Snapshot)
        self.snapshots += 1
        assert observation.clk in ("0", "1"), "Source clock must always be known"
        invalid = {name for name in CONTROLS if getattr(observation, name) not in ("0", "1")}
        if invalid:
            # Expected assertion failures exercise the illegal-control checker.
            # All other unknown controls terminate the test immediately.
            assert observation.expected_unknown is not None, f"Unexpected unknown controls: {invalid}"
            name, value = observation.expected_unknown
            assert invalid == {name} and getattr(observation, name) == value
            other = getattr(observation, CONTROLS[1 - CONTROLS.index(name)])
            diagnostic = (name, value, other, "low" if observation.clk == "0" else "high")
            if diagnostic not in self.unknown_controls:
                self.logger.info("Expected known-control assertion: %s", diagnostic)
            self.unknown_controls.add(diagnostic)
        else:
            self.combinations.add((observation.enable, observation.test_enable))

        if observation.clk == "0":
            self.latched = effective_enable(observation.enable, observation.test_enable)
        expected = "0" if observation.clk == "0" else self.latched
        assert observation.gclk == expected, (
            f"{observation.label} at {observation.time_ps} ps: o_gclk={observation.gclk}, "
            f"expected {expected}; clk={observation.clk}, captured enable={self.latched}"
        )
        if expected != self.expected_output:
            self.expected_changes.append((observation.time_ps, self.expected_output, expected))
        self.expected_output = expected

        previous = self.previous
        if previous is not None:
            phase = "low" if observation.clk == "0" else "high"
            for name in CONTROLS:
                before, after = getattr(previous, name), getattr(observation, name)
                if before != after and before in ("0", "1") and after in ("0", "1"):
                    self.half_cycle_transitions.add((name, after, phase))
                    self.requests.append({
                        "time_ps": observation.time_ps, "control": name,
                        "requested_value": after, "phase": phase,
                        "captured_enable": self.latched,
                    })
            if observation.clk != previous.clk:
                edge = "rise" if observation.clk == "1" else "fall"
                self.source_edges.append((observation.time_ps, edge))
                if edge == "rise":
                    self.decisions.append({
                        "time_ps": observation.time_ps, "captured_enable": self.latched,
                        "actual_output": observation.gclk,
                        "enable": observation.enable, "test_enable": observation.test_enable,
                        "label": observation.label,
                    })
        self.previous = observation

    def report(self):
        actual = [(edge.time_ps, edge.previous, edge.current) for edge in self.output_changes]
        # This comparison rejects extra edges even when the settled value and
        # the total number of propagated cycles happen to be correct.
        mismatch = next((pair for pair in zip_longest(actual, self.expected_changes) if pair[0] != pair[1]), None)
        assert mismatch is None, (
            f"Output transition history differs from the independent model: "
            f"actual={mismatch[0]}, expected={mismatch[1]}"
        )
        high_widths, low_widths = [], []
        rise, fall = None, None
        for edge in self.output_changes:
            if (edge.previous, edge.current) == ("0", "1"):
                assert edge.source_level == "1", "Output rose while source clock was low"
                assert (edge.time_ps, "rise") in self.source_edges, "Output rose without a source rising edge"
                if fall is not None:
                    low_widths.append(edge.time_ps - fall)
                    assert low_widths[-1] >= self.config.half_ps, "Output low pulse is too short"
                rise = edge.time_ps
            elif (edge.previous, edge.current) == ("1", "0"):
                assert edge.source_level == "0", "Output fell while source clock was high"
                assert (edge.time_ps, "fall") in self.source_edges, "Output fell without a source falling edge"
                assert rise is not None, "Output high pulse has no rising edge"
                high_widths.append(edge.time_ps - rise)
                assert high_widths[-1] == self.config.half_ps, "Output high pulse was truncated or extended"
                fall, rise = edge.time_ps, None
            else:
                # Illegal controls may produce X; their exact four-state
                # transitions are checked above, not counted as legal pulses.
                rise, fall = None, None
        assert rise is None, "Simulation ended with an incomplete output pulse"

        near_edges = set()
        source_times = [time for time, _ in self.source_edges]
        rise_times = [decision["time_ps"] for decision in self.decisions]
        for request in self.requests:
            time = request["time_ps"]
            for edge_time, edge_kind in self.source_edges[bisect_left(source_times, time - 1):bisect_right(source_times, time + 1)]:
                if abs(edge_time - time) == 1:
                    near_edges.add((request["control"], request["requested_value"], edge_kind,
                                    "before" if time < edge_time else "after"))
            following_index = bisect_right(rise_times, time)
            following = self.decisions[following_index] if following_index < len(self.decisions) else None
            request["next_source_rise_ps"] = following["time_ps"] if following else None
            request["next_pulse_propagated"] = following["actual_output"] if following else None

        runs = []
        for decision in self.decisions:
            value = decision["captured_enable"]
            if runs and runs[-1][0] == value:
                runs[-1][1] += 1
            else:
                runs.append([value, 1])
        enabled_runs = [length for value, length in runs if value == "1"]
        disabled_runs = [length for value, length in runs if value == "0"]
        consecutive_changes = 0
        longest_changes = 0
        for previous, current in zip(self.decisions, self.decisions[1:]):
            changed = {previous["captured_enable"], current["captured_enable"]} == {"0", "1"}
            consecutive_changes = consecutive_changes + 1 if changed else 0
            longest_changes = max(longest_changes, consecutive_changes)
        random_cycles = sum(decision["label"].startswith("random_") for decision in self.decisions)
        scan_values = {
            decision["enable"] for decision in self.decisions
            if decision["label"].startswith("scan_") and decision["test_enable"] == "1"
            and decision["actual_output"] == "1"
        }
        goals = {
            "startup": self.decisions[0]["actual_output"] == str(int(self.config.startup_enabled)),
            "control_half_cycle_transitions": set(product(CONTROLS, ("0", "1"), ("low", "high"))) <= self.half_cycle_transitions,
            "control_combinations": set(product(("0", "1"), repeat=2)) <= self.combinations,
            "near_both_edges": set(product(CONTROLS, ("0", "1"), ("rise", "fall"), ("before", "after"))) <= near_edges,
            "zero_propagated_pulses": bool(disabled_runs),
            "one_propagated_pulse": 1 in enabled_runs,
            "multiple_propagated_pulses": max(enabled_runs, default=0) >= 3,
            "short_disabled_interval": any(length <= 2 for length in disabled_runs),
            "long_disabled_interval": max(disabled_runs, default=0) >= 64,
            "long_enabled_interval": max(enabled_runs, default=0) >= 64,
            "back_to_back_gating": longest_changes >= 4,
            "scan_override": scan_values == {"0", "1"},
            "random_activity": random_cycles >= self.config.random_cycles,
            "unknown_controls": set(product(CONTROLS, ("x", "z"), ("0", "1"), ("low", "high"))) <= self.unknown_controls,
            "complete_output_pulses": bool(high_widths) and len(high_widths) == sum(
                (edge.previous, edge.current) == ("0", "1") for edge in self.output_changes
            ),
        }
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "startup_enabled": self.config.startup_enabled,
            "seed": self.config.seed, "simulator": cocotb.SIM_NAME,
            "source_cycles": len(self.decisions), "random_cycles": random_cycles,
            "snapshots_checked": self.snapshots,
            "output_transitions_checked": len(actual), "complete_high_pulses": len(high_widths),
            "high_width_ps": {"minimum": min(high_widths, default=0), "maximum": max(high_widths, default=0)},
            "minimum_low_width_ps": min(low_widths, default=0),
            "expected_control_diagnostics": len(self.unknown_controls),
            "longest_enabled_interval": max(enabled_runs, default=0),
            "longest_disabled_interval": max(disabled_runs, default=0),
            "goals": goals,
            "bins": {
                "control_transitions": sorted(self.half_cycle_transitions),
                "control_combinations": sorted(self.combinations),
                "near_edges": sorted(near_edges), "unknown_controls": sorted(self.unknown_controls),
            },
            "requested_transitions": self.requests,
            "source_pulse_decisions": self.decisions,
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing clock gate coverage: {missing}"
        self.logger.info("Clock gate PASS: %d cycles, %d output transitions, %d complete pulses",
                         report["source_cycles"], report["output_transitions_checked"], report["complete_high_pulses"])


class ClockGateEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = ClockGateDriver("driver", self)
        self.monitor = ClockGateMonitor("monitor", self)
        self.scoreboard = ClockGateScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
