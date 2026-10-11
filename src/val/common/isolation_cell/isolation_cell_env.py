"""Port-only, four-state PyUVM verification of the portable isolation boundary."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import product
import json
import math
import os
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import (
    ConfigDB, uvm_analysis_export, uvm_analysis_port, uvm_driver, uvm_env,
    uvm_monitor, uvm_scoreboard, uvm_sequencer, uvm_sequence_item,
)


@dataclass(frozen=True)
class IsolationCellConfig:
    width: int
    clamp_value: int
    active_high: bool
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> IsolationCellConfig:
        polarity = os.getenv("ISOLATION_CELL_ACTIVE_HIGH", "1")
        assert polarity in ("0", "1"), "Control polarity must be a static boolean"
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/isolation_cell/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("ISOLATION_CELL_WIDTH", str(len(cocotb.top.o_data)))),
            clamp_value=int(os.getenv("ISOLATION_CELL_CLAMP_VALUE", "0"), 0),
            active_high=polarity == "1", seed=int(os.getenv("ISOLATION_CELL_SEED", "20261011")),
            random_cycles=int(os.getenv("ISOLATION_CELL_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("ISOLATION_CELL_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.width >= 1 and 0 <= config.clamp_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 randomized transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def active_control(self) -> int:
        return int(self.active_high)

    @property
    def inactive_control(self) -> int:
        return 1 - self.active_control

    @property
    def clamp_bits(self) -> str:
        return f"{self.clamp_value:0{self.width}b}"

    @property
    def clamp_class(self) -> str:
        return "zero" if self.clamp_value == 0 else "one" if self.clamp_value == self.maximum else "mixed"

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    @property
    def directed_patterns(self) -> tuple[str, ...]:
        """Required finite patterns, with exhaustive binary data through width 4."""
        values = {0, self.maximum, self.clamp_value, self.clamp_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.width))
        values.update(int((pattern * self.width)[:self.width], 2) for pattern in ("01", "10"))
        if self.width <= 4:
            values.update(range(self.maximum + 1))
        patterns = {f"{value:0{self.width}b}" for value in values}
        patterns.update(value * self.width for value in ("x", "z"))
        for bit, unknown, background in product(range(self.width), ("x", "z"), ("0", "1")):
            vector = [background] * self.width
            vector[bit] = unknown
            patterns.add("".join(vector))
        if self.width > 1:
            patterns.update((value * self.width)[:self.width] for value in ("xz", "zx"))
        return tuple(sorted(patterns))


@dataclass(frozen=True)
class Inputs:
    isolate: int | str
    data: int | str

    def data_bits(self, width: int) -> str:
        if isinstance(self.data, int):
            assert 0 <= self.data < 1 << width, "Do not truncate source data"
            return f"{self.data:0{width}b}"
        assert len(self.data) == width and set(self.data.lower()) <= set("01xz")
        return self.data.lower()


def isolation_state(control: str, active_high: bool) -> str:
    if control not in ("0", "1"):
        return "unknown"
    return "active" if int(control) == int(active_high) else "inactive"


def expected_data(data: str, control: str, clamp: str, active_high: bool) -> str:
    """Merge each unknown-control bit independently; preserve inactive X/Z data."""
    state = isolation_state(control, active_high)
    if state == "inactive":
        return data
    if state == "active":
        return clamp
    return "".join(bit if bit == clamp_bit else "x" for bit, clamp_bit in zip(data, clamp, strict=True))


def pattern_classes(data: str) -> set[str]:
    classes = set()
    width = len(data)
    if set(data) <= {"0", "1"}:
        value, maximum = int(data, 2), (1 << width) - 1
        if value == 0:
            classes.add("zero")
        if value == maximum:
            classes.add("one")
        if value.bit_count() == 1:
            classes.add("walking_one")
        if (value ^ maximum).bit_count() == 1:
            classes.add("walking_zero")
        if data in (("01" * width)[:width], ("10" * width)[:width]):
            classes.add("alternating")
    if data == "x" * width:
        classes.add("all_x")
    if data == "z" * width:
        classes.add("all_z")
    if {"x", "z"} <= set(data):
        classes.add("mixed_x_z")
    return classes


class IsolationCellItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, unknown=None):
        super().__init__(label)
        self.inputs = inputs
        self.unknown = unknown


@dataclass(frozen=True)
class Observation:
    label: str
    isolate: str
    data: str
    output: str
    requested: Inputs
    expected_unknown: str | None
    continuously_isolated: bool


@dataclass(frozen=True)
class OutputActivity:
    value: str
    continuously_isolated: bool


class IsolationCellDriver(uvm_driver):
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
            # Clamp assertion/release may change the output. Only an interval
            # that starts and stays isolated is required to have no activity.
            self.active["quiet"] = (
                str(self.dut.i_isolate.value) == str(self.config.active_control)
                and item.inputs.isolate == self.config.active_control
            )
            self.dut.i_isolate.value = item.inputs.isolate
            self.dut.i_data.value = item.inputs.data_bits(self.config.width)
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "The monitor did not consume the sample"
            self.seq_item_port.item_done()


class IsolationCellMonitor(uvm_monitor):
    """Sample actual ports and capture every observable isolated output change."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self):
        while True:
            await self.dut.o_data.value_change
            # Re-arm immediately so a glitch cannot hide before ReadOnly.
            self.ap.write(OutputActivity(str(self.dut.o_data.value).lower(), self.active["quiet"]))

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        output_task = cocotb.start_soon(self.output_activity())
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(self.dut.i_isolate.value).lower(),
                    str(self.dut.i_data.value).lower(), str(self.dut.o_data.value).lower(),
                    item.inputs, item.unknown, self.active["quiet"],
                ))
                self.active["sample"].clear()
        finally:
            output_task.cancel()


class IsolationCellScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.checks = self.random_checks = self.control_violations = self.output_transitions = 0
        self.states = Counter()
        self.passed_bits = set()
        self.clamped_bits = set()
        self.assert_patterns = set()
        self.release_patterns = set()
        self.quiet_patterns = set()
        self.activity_states = set()
        self.control_unknowns = set()
        self.merge_bins = set()
        self.patterns_by_state = defaultdict(set)
        self.exhaustive = set()

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.continuously_isolated, (
                f"Source activity changed an isolated output to {observation.value}"
            )
            self.output_transitions += 1
            return
        assert isinstance(observation, Observation)
        config = self.config
        assert observation.isolate == str(observation.requested.isolate).lower(), "Isolation control was coerced"
        assert observation.data == observation.requested.data_bits(config.width), "Source data was coerced"
        illegal = observation.isolate if observation.isolate not in ("0", "1") else None
        assert illegal == observation.expected_unknown, (
            f"{observation.label}: known-control assertion {illegal}, expected {observation.expected_unknown}"
        )
        if illegal:
            if illegal not in self.control_unknowns:
                self.logger.info("Expected known-control assertion: i_isolate=%s", illegal)
            self.control_unknowns.add(illegal)
            self.control_violations += 1
        expected = expected_data(observation.data, observation.isolate, config.clamp_bits, config.active_high)
        assert observation.output == expected, (
            f"{observation.label}: control={observation.isolate}, data={observation.data}, "
            f"output={observation.output}, expected={expected}"
        )
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        state = isolation_state(observation.isolate, config.active_high)
        self.states[state] += 1
        self.patterns_by_state[state].update(pattern_classes(observation.data))
        if config.width <= 4:
            self.exhaustive.add((observation.isolate, observation.data))
        if state == "inactive":
            self.passed_bits.update(enumerate(reversed(observation.output)))
        elif state == "active":
            assert set(observation.output) <= {"0", "1"}, "An isolated output became unknown"
            self.clamped_bits.update(range(config.width))
            if observation.continuously_isolated:
                self.quiet_patterns.add(observation.data)
        else:
            for bit, (value, clamp) in enumerate(zip(reversed(observation.data), reversed(config.clamp_bits), strict=True)):
                relation = "equal" if value == clamp else value if value in ("x", "z") else "different"
                self.merge_bins.add((bit, observation.isolate, relation))
        previous = self.previous
        if previous:
            before = isolation_state(previous.isolate, config.active_high)
            if before == "inactive" and state == "active" and previous.data == observation.data:
                self.assert_patterns.add(observation.data)
            if before == "active" and state == "inactive" and previous.data == observation.data:
                self.release_patterns.add(observation.data)
            if before == state and previous.data != observation.data:
                self.activity_states.add(state)
        self.previous = observation

    def report(self):
        config = self.config
        patterns = set(config.directed_patterns)
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.width > 1:
            classes.add("mixed_x_z")
        goals = {
            "all_isolation_states": set(self.states) == {"active", "inactive", "unknown"},
            "every_bit_passes_all_four_states": set(product(range(config.width), "01xz")) <= self.passed_bits,
            "every_bit_clamps": self.clamped_bits == set(range(config.width)),
            "assertion_every_directed_pattern": patterns <= self.assert_patterns,
            "release_every_directed_pattern": patterns <= self.release_patterns,
            "isolated_data_activity_no_output_changes": patterns <= self.quiet_patterns,
            "data_activity_before_during_after_isolation": {"active", "inactive"} <= self.activity_states,
            "all_pattern_classes_pass_and_clamp": all(classes <= self.patterns_by_state[state] for state in ("active", "inactive")),
            "unknown_control_assertions": self.control_unknowns == {"x", "z"},
            "unknown_control_merge_every_bit": set(product(range(config.width), ("x", "z"), ("equal", "different", "x", "z"))) <= self.merge_bins,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 4:
            words = ("".join(bits) for bits in product("01xz", repeat=config.width))
            goals["exhaustive_four_state_truth_table"] = set(product("01xz", words)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "CLAMP_VALUE": config.clamp_value,
                           "ISOLATE_ACTIVE_HIGH": int(config.active_high)},
            "clamp_class": config.clamp_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "random_transactions": self.random_checks,
            "output_transitions": self.output_transitions, "expected_control_violations": self.control_violations,
            "goals": goals, "passed_bit_coverage_percent": 100 * len(self.passed_bits) / (4 * config.width),
            "bins": {"isolation_states": dict(self.states), "passed_bit_values": sorted(self.passed_bits),
                     "clamped_bits": sorted(self.clamped_bits), "assert_patterns": sorted(self.assert_patterns),
                     "release_patterns": sorted(self.release_patterns), "quiet_patterns": sorted(self.quiet_patterns),
                     "data_activity_states": sorted(self.activity_states), "unknown_controls": sorted(self.control_unknowns),
                     "merge_bins": sorted(self.merge_bins), "pattern_classes": {key: sorted(value) for key, value in self.patterns_by_state.items()},
                     "four_state_truth_table_entries": len(self.exhaustive) if config.width <= 4 else None},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing isolation cell coverage: {missing}"
        self.logger.info("Isolation cell coverage PASS: %d transactions", self.checks)


class IsolationCellEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = IsolationCellDriver("driver", self)
        self.monitor = IsolationCellMonitor("monitor", self)
        self.scoreboard = IsolationCellScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
