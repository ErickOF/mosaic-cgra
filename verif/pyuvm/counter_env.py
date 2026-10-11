"""PyUVM counter components and a model derived from the counter specification."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

import cocotb
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer
from pyuvm import (
    ConfigDB,
    uvm_analysis_export,
    uvm_analysis_port,
    uvm_driver,
    uvm_env,
    uvm_monitor,
    uvm_scoreboard,
    uvm_sequencer,
    uvm_sequence_item,
)


CONTROLS = ("rstb", "clear", "load", "enable", "direction")
COMMANDS = ("reset", "clear", "load", "increment", "decrement", "hold")


@dataclass(frozen=True)
class CounterConfig:
    """Expected elaboration parameters and reproducible campaign settings."""
    width: int
    reset_value: int
    saturate: bool
    async_reset: bool
    seed: int
    random_cycles: int
    clock_ns: float
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> CounterConfig:
        config = cls(
            width=int(os.getenv("COUNTER_WIDTH", "32")),
            reset_value=int(os.getenv("COUNTER_RESET_VALUE", "0"), 0),
            saturate=bool(int(os.getenv("COUNTER_SATURATE", "1"))),
            async_reset=bool(int(os.getenv("COUNTER_ASYNC_RESET", "0"))),
            seed=int(os.getenv("COUNTER_SEED", "20261010")),
            random_cycles=int(os.getenv("COUNTER_RANDOM_CYCLES", "2000")),
            clock_ns=float(os.getenv("TEST_CLOCK_PERIOD_NS", "4")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("COUNTER_COVERAGE_FILE", "counter_coverage.json")),
        )
        assert config.width >= 1
        assert 0 <= config.reset_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 randomized cycles"
        assert config.clock_ns > 0
        assert 0 <= config.settle_ns < config.clock_ns / 2
        assert config.sample_ns + 0.001 < config.clock_ns / 2
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def sample_ns(self) -> float:
        # Advance beyond the edge even for zero-delay RTL before ReadOnly.
        return max(self.settle_ns, 0.001)

    @property
    def representative_values(self) -> set[int]:
        return {
            0, 1, self.maximum, self.maximum - 1, self.reset_value,
            self.maximum // 2, 0xA55A & self.maximum,
        }


@dataclass(frozen=True)
class Inputs:
    """Controls observed on the interface; strings preserve X/Z values."""

    rstb: int | str = 1
    clear: int | str = 0
    load: int | str = 0
    enable: int | str = 0
    direction: int | str = 0
    load_value: int = 0

    @property
    def invalid_controls(self) -> set[str]:
        return {name for name in CONTROLS if getattr(self, name) not in (0, 1)}

    @property
    def command(self) -> str:
        if not self.rstb:
            return "reset"
        if self.clear:
            return "clear"
        if self.load:
            return "load"
        if self.enable:
            return "decrement" if self.direction else "increment"
        return "hold"


@dataclass(frozen=True)
class State:
    count: int
    overflow: int = 0
    underflow: int = 0


def next_state(config: CounterConfig, state: State | None, inputs: Inputs) -> State:
    """Apply the specified command priority and bounded integer arithmetic."""
    command = inputs.command
    if command in ("reset", "clear"):
        return State(config.reset_value)
    if command == "load":
        return State(inputs.load_value)
    assert state is not None, "Recover from illegal controls with reset or load"
    if command == "hold":
        return State(state.count)
    candidate = state.count + (-1 if command == "decrement" else 1)
    count = (
        min(max(candidate, 0), config.maximum)
        if config.saturate else candidate & config.maximum
    )
    return State(count, int(candidate > config.maximum), int(candidate < 0))


class CounterItem(uvm_sequence_item):
    """One clocked command, optionally including a short reset pulse."""

    def __init__(self, name, inputs, *, unknown=None, pulse_reset=False):
        super().__init__(name)
        self.inputs = inputs
        self.unknown = unknown
        self.pulse_reset = pulse_reset


@dataclass(frozen=True)
class Observation:
    label: str
    mid_inputs: Inputs
    edge_inputs: Inputs
    mid_state: State
    edge_state: State
    mid_terminal: int
    edge_terminal: int
    expected_unknown: str | None
    pulse_reset: bool


class CounterDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        # The test starts with reset asserted. Complete one initialization
        # edge before observing a synchronous counter's otherwise unknown state.
        await RisingEdge(self.dut.i_clk)
        while True:
            item = await self.seq_item_port.get_next_item()
            await FallingEdge(self.dut.i_clk)
            self.active["item"] = item
            for name, value in asdict(item.inputs).items():
                getattr(self.dut, f"i_{name}").value = value
            if item.pulse_reset:
                # Assert while the clock is low and release before its next
                # rising edge. Only an asynchronous counter may reset here.
                await Timer(self.config.clock_ns * 3 / 8, unit="ns")
                self.dut.i_rstb.value = 1
            await RisingEdge(self.dut.i_clk)
            await Timer(self.config.sample_ns, unit="ns")
            await ReadOnly()
            # Allow the passive monitor and scoreboard to complete before
            # finish_item can let the test drop its final objection.
            await Timer(1, unit="ps")
            self.active["item"] = None
            self.seq_item_port.item_done()


class CounterMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    def inputs(self) -> Inputs:
        values = {}
        for name in CONTROLS:
            value = getattr(self.dut, f"i_{name}").value
            values[name] = int(value) if value.is_resolvable else str(value).lower()
        return Inputs(**values, load_value=int(self.dut.i_load_value.value))

    def state(self) -> State:
        return State(
            int(self.dut.o_count.value), int(self.dut.o_overflow.value),
            int(self.dut.o_underflow.value),
        )

    async def run_phase(self):
        while True:
            await FallingEdge(self.dut.i_clk)
            await Timer(self.config.clock_ns / 4, unit="ns")
            await ReadOnly()
            item = self.active["item"]
            if item is None:
                continue
            mid_inputs = self.inputs()
            mid_state = self.state()
            mid_terminal = int(self.dut.o_terminal.value)
            await RisingEdge(self.dut.i_clk)
            edge_inputs = self.inputs()
            await Timer(self.config.sample_ns, unit="ns")
            await ReadOnly()
            self.ap.write(Observation(
                item.get_name(), mid_inputs, edge_inputs, mid_state, self.state(),
                mid_terminal, int(self.dut.o_terminal.value), item.unknown,
                item.pulse_reset,
            ))


class FunctionalCoverage:
    """Require positive hits for the specification's functional bins/crosses."""

    def __init__(self, config):
        self.config = config
        self.commands = set()
        self.command_direction = set()
        self.control_combinations = set()
        self.values = set()
        self.loaded_values = set()
        self.reset_from = set()
        self.state_controls = set()
        self.unknown_controls = set()
        self.disabled_terminal = set()
        self.events = Counter()
        self.checks = 0
        self.random_cycles = 0
        self.run_command = None
        self.run_length = 0
        self.longest_hold = 0
        self.longest_active = 0

    def sample(self, observation, previous, current):
        inputs = observation.edge_inputs
        command = inputs.command
        self.checks += 1
        self.commands.add(command)
        self.command_direction.add((command, inputs.direction))
        controls = tuple(getattr(inputs, name) for name in CONTROLS)
        self.control_combinations.add(controls)
        self.values.add(current.count)
        self.random_cycles += observation.label.startswith("random_")
        if command == "load":
            self.loaded_values.add(inputs.load_value)
        if previous is not None:
            self.state_controls.add((previous.count, *controls))
            if command == "reset":
                self.reset_from.add(previous.count)
            if command == "increment" and previous.count == self.config.maximum - 1:
                self.events["increment_to_maximum"] += 1
            if command == "decrement" and previous.count == 1:
                self.events["decrement_to_zero"] += 1
            if previous.overflow and command == "decrement":
                self.events["overflow_then_decrement"] += 1
            if previous.underflow and command == "increment":
                self.events["underflow_then_increment"] += 1
        self.events["overflow"] += current.overflow
        self.events["underflow"] += current.underflow
        self.events["short_reset_pulse"] += observation.pulse_reset
        if command == "hold" and current.count in (0, self.config.maximum):
            boundary = "zero" if current.count == 0 else "maximum"
            self.disabled_terminal.add((boundary, inputs.direction))
        self.events["direction_change"] += (
            getattr(self, "last_direction", inputs.direction) != inputs.direction
        )
        self.last_direction = inputs.direction
        run_command = "active" if command in ("increment", "decrement") else command
        self.run_length = self.run_length + 1 if run_command == self.run_command else 1
        self.run_command = run_command
        if run_command == "hold":
            self.longest_hold = max(self.longest_hold, self.run_length)
        if run_command == "active":
            self.longest_active = max(self.longest_active, self.run_length)

    def report(self):
        config = self.config
        # Exhaustive reset-state sampling is finite for small widths. Wider
        # counters use boundary, reset, pattern, and randomized values.
        required_reset = (
            set(range(config.maximum + 1)) if config.width <= 8
            else config.representative_values
        )
        goals = {
            "commands": set(COMMANDS) <= self.commands,
            # Arithmetic command names already encode direction; the opposite
            # direction bins for increment/decrement are structurally illegal.
            "command_direction_cross": (
                set(product(("reset", "clear", "load", "hold"), (0, 1)))
                | {("increment", 0), ("decrement", 1)}
            ) <= self.command_direction,
            "control_priority_cross": set(product((0, 1), repeat=5)) <= self.control_combinations,
            "zero_maximum_reset_values": {0, config.maximum, config.reset_value} <= self.values,
            "representative_loads": config.representative_values <= self.loaded_values,
            "reset_states": required_reset <= self.reset_from,
            "disabled_terminal_direction_cross": set(product(("zero", "maximum"), (0, 1))) <= self.disabled_terminal,
            "unknown_controls": set(product(CONTROLS, ("x", "z"))) <= self.unknown_controls,
            "long_hold": self.longest_hold >= 32,
            "long_active": self.longest_active >= 64,
            "long_random_sequence": self.random_cycles >= config.random_cycles,
        }
        for event in (
            "increment_to_maximum", "decrement_to_zero", "overflow", "underflow",
            "overflow_then_decrement", "underflow_then_increment",
            "direction_change", "short_reset_pulse",
        ):
            goals[event] = self.events[event] > 0
        if config.width <= 4:
            goals["exhaustive_state_control_cross"] = all(
                (value, *controls) in self.state_controls
                for value in range(config.maximum + 1)
                for controls in product((0, 1), repeat=5)
            )
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {
                "WIDTH": config.width, "RESET_VALUE": config.reset_value,
                "SATURATE": int(config.saturate), "ASYNC_RESET": int(config.async_reset),
            },
            "seed": config.seed,
            "checked_cycles": self.checks,
            "random_cycles": self.random_cycles,
            "expected_control_assertions": len(self.unknown_controls),
            "reset_states_checked": len(self.reset_from),
            "reset_states_exhaustive": config.width <= 8,
            "longest_hold": self.longest_hold,
            "longest_active": self.longest_active,
            "events": dict(self.events),
            "bins": {
                "commands": sorted(self.commands),
                "command_direction": sorted(self.command_direction),
                "control_combinations": sorted(self.control_combinations),
                "loaded_values": sorted(self.loaded_values),
                "reset_from_values": sorted(self.reset_from),
                "disabled_terminal": sorted(self.disabled_terminal),
                "unknown_controls": sorted(self.unknown_controls),
                "state_control_combinations": len(self.state_controls),
            },
            "goals": goals,
        }


class CounterScoreboard(uvm_scoreboard):
    """Assert registered, combinational, reset, and legal-control behavior."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.state = State(self.config.reset_value)
        self.coverage = FunctionalCoverage(self.config)
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write

    def check_terminal(self, state, direction, terminal, label):
        expected = (
            int(state.count == (0 if direction else self.config.maximum))
            if direction in (0, 1) else 0
        )
        assert terminal == expected, f"{label}: terminal {terminal}, expected {expected}"

    def write(self, observation):
        mid = observation.mid_inputs
        edge = observation.edge_inputs
        invalid = mid.invalid_controls | edge.invalid_controls
        if invalid:
            # These are intentional negative tests of the known-control
            # assertions. Do not predict unspecified arithmetic from X/Z.
            assert invalid == {observation.expected_unknown}, (
                f"{observation.label}: unexpected unknown controls {invalid}"
            )
            for name in invalid:
                self.coverage.unknown_controls.add((name, getattr(mid, name)))
            if "direction" in invalid:
                assert observation.mid_terminal == observation.edge_terminal == 0, (
                    "Unknown direction must force terminal low"
                )
            self.state = None
            self.logger.info("Expected known-control assertion: %s", observation.label)
            return
        assert observation.expected_unknown is None, (
            "The simulator resolved an injected X/Z; four-state verification is required"
        )
        previous = self.state
        before_edge = (
            State(self.config.reset_value)
            if self.config.async_reset and mid.rstb == 0 else previous
        )
        if before_edge is not None:
            assert observation.mid_state == before_edge, (
                f"{observation.label}: mid-cycle state {observation.mid_state}, expected {before_edge}"
            )
            self.check_terminal(before_edge, mid.direction, observation.mid_terminal, observation.label)
        expected = next_state(self.config, before_edge, edge)
        assert observation.edge_state == expected, (
            f"{observation.label}: state {observation.edge_state}, expected {expected}; inputs={edge}"
        )
        assert not (expected.overflow and expected.underflow)
        self.check_terminal(expected, edge.direction, observation.edge_terminal, observation.label)
        self.coverage.sample(observation, previous, expected)
        self.state = expected

    def check_phase(self):
        report = self.coverage.report()
        report["simulator"] = cocotb.SIM_NAME
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8",
        )
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing functional coverage: {missing}"
        self.logger.info("Counter coverage PASS: %d cycles, %d goals", report["checked_cycles"], len(report["goals"]))


class CounterEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = CounterDriver("driver", self)
        self.monitor = CounterMonitor("monitor", self)
        self.scoreboard = CounterScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
