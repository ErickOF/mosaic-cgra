"""Port-only PyUVM checks for architectural operand isolation.

Four-state comparisons preserve individual bits and distinguish this primitive
from a power-domain isolation cell. Output activity checks apply while controls
remain fixed; asynchronous control switching has no glitch-free guarantee.
"""

from __future__ import annotations

from collections import Counter
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
class OperandIsolationConfig:
    width: int
    clamp_value: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> OperandIsolationConfig:
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/operand_isolation/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("OPERAND_ISOLATION_WIDTH", str(len(cocotb.top.o_data)))),
            clamp_value=int(os.getenv("OPERAND_ISOLATION_CLAMP_VALUE", "0"), 0),
            seed=int(os.getenv("OPERAND_ISOLATION_SEED", "20261011")),
            random_cycles=int(os.getenv("OPERAND_ISOLATION_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("OPERAND_ISOLATION_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and 0 <= config.clamp_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

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
    def patterns(self) -> tuple[str, ...]:
        values = {0, self.maximum, self.clamp_value, self.clamp_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.width))
        values.update(int((pattern * self.width)[:self.width], 2) for pattern in ("01", "10"))
        patterns = {f"{value:0{self.width}b}" for value in values}
        patterns.update(state * self.width for state in "xz")
        for bit, state, background in product(range(self.width), "xz", "01"):
            word = [background] * self.width
            word[self.width - bit - 1] = state
            patterns.add("".join(word))
        if self.width > 1:
            patterns.update((word * self.width)[:self.width] for word in ("xz", "zx"))
        return tuple(sorted(patterns))


def bits(value: int | str, width: int) -> str:
    """Reject truncation instead of silently weakening the stimulus."""
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Stimulus does not fit the port"
        return f"{value:0{width}b}"
    result = value.lower()
    assert len(result) == width and set(result) <= set("01xz"), "Invalid four-state stimulus"
    return result


def expected_data(data: str, isolate: str, clamp: str) -> str:
    """An unknown request poisons the entire operand, even equal clamp bits."""
    return {"0": data, "1": clamp}.get(isolate, "x" * len(data))


def pattern_classes(word: str) -> set[str]:
    classes = set()
    for state, name in (("0", "zero"), ("1", "one"), ("x", "all_x"), ("z", "all_z")):
        if word == state * len(word):
            classes.add(name)
    if set(word) <= {"0", "1"}:
        if word.count("1") == 1:
            classes.add("walking_one")
        if word.count("0") == 1:
            classes.add("walking_zero")
        if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
            classes.add("alternating")
    if set(word) & {"0", "1"} and set(word) & {"x", "z"}:
        classes.add("partial_unknown")
    if {"x", "z"} <= set(word):
        classes.add("mixed_x_z")
    return classes


@dataclass(frozen=True)
class Inputs:
    data: int | str
    isolate: int | str


class OperandIsolationItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, expected_unknown=None, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.inputs = inputs
        self.expected_unknown = expected_unknown
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    data: str
    isolate: str
    output: str
    requested: Inputs
    expected_unknown: str | None
    stage: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    value: str
    quiet: bool


class OperandIsolationDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            data, control = bits(item.inputs.data, self.config.width), bits(item.inputs.isolate, 1)
            old_control = str(cocotb.top.i_isolate.value).lower()
            old_data = str(cocotb.top.i_data.value).lower()
            self.active.update(item=item, stage="settled", quiet=(
                old_control == control and (control != "0" or old_data == data)
            ))
            cocotb.top.i_data.value = data
            cocotb.top.i_isolate.value = control
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            self.active["quiet"] = True
            await Timer(item.hold_ns, unit="ns")
            assert not self.active["sample"].is_set(), "Monitor missed the settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()


class OperandIsolationMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self):
        previous = str(cocotb.top.o_data.value).lower()
        while True:
            await cocotb.top.o_data.value_change
            quiet = self.active["quiet"]
            # Sample after combinational delta cycles. Finite pulses persisting
            # into this phase are detected even between transaction samples.
            await ReadOnly()
            value = str(cocotb.top.o_data.value).lower()
            if value != previous:
                self.ap.write(OutputActivity(value, quiet))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        activity_task = cocotb.start_soon(self.output_activity())
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_data.value).lower(),
                    str(cocotb.top.i_isolate.value).lower(), str(cocotb.top.o_data.value).lower(),
                    item.inputs, item.expected_unknown, self.active["stage"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            activity_task.cancel()


class OperandIsolationScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.controls = []
        self.checks = self.held_checks = self.random_checks = self.output_transitions = 0
        self.states = Counter()
        self.control_violations = Counter()
        self.bit_values = set()
        self.patterns = set()
        self.state_activity = set()
        self.transitions = set()
        self.bit_transitions = set()
        self.unknown_relations = set()
        self.back_to_back = set()
        self.holds = set()
        self.exhaustive = set()

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.quiet, f"Isolated/stable input activity changed o_data to {observation.value}"
            self.output_transitions += 1
            return
        config = self.config
        assert observation.data == bits(observation.requested.data, config.width), "Data stimulus was coerced"
        assert observation.isolate == bits(observation.requested.isolate, 1), "Control stimulus was coerced"
        # Expected negative stimulus acknowledges a real assertion violation.
        # Untagged X/Z controls remain fatal; the runner proves this separately.
        try:
            assert observation.isolate in ("0", "1"), f"Known-control assertion failed: i_isolate={observation.isolate}"
        except AssertionError:
            if observation.expected_unknown != observation.isolate:
                raise
            if observation.stage == "settled":
                if not self.control_violations[observation.isolate]:
                    self.logger.info("Expected known-control assertion: i_isolate=%s", observation.isolate)
                self.control_violations[observation.isolate] += 1
        else:
            assert observation.expected_unknown is None, "Expected an unknown control but received a known value"
        expected = expected_data(observation.data, observation.isolate, config.clamp_bits)
        assert observation.output == expected, (
            f"{observation.label}/{observation.stage}: control={observation.isolate}, "
            f"data={observation.data}, output={observation.output}, expected={expected}"
        )
        if observation.stage == "held":
            self.held_checks += 1
            self.holds.add((observation.isolate, "long" if observation.hold_ns >= 1 else "short"))
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        control = observation.isolate
        self.states[control] += 1
        self.patterns.update((control, name) for name in pattern_classes(observation.data))
        self.bit_values.update((control, bit, value) for bit, value in enumerate(reversed(observation.data)))
        if control in "xz":
            for bit, (value, clamp) in enumerate(zip(reversed(observation.data), reversed(config.clamp_bits), strict=True)):
                relation = "equal" if value == clamp else value if value in "xz" else "different"
                self.unknown_relations.add((control, bit, relation))
        if config.width <= 8:
            self.exhaustive.add((control, observation.data))
        previous = self.previous
        if previous:
            changed = previous.data != observation.data
            self.transitions.add((previous.isolate, control, changed))
            if previous.isolate == control:
                self.state_activity.add((control, changed))
                self.bit_transitions.update(
                    (control, bit, before, after)
                    for bit, (before, after) in enumerate(zip(reversed(previous.data), reversed(observation.data), strict=True))
                    if before != after
                )
        self.controls.append(control)
        if len(self.controls) >= 3:
            self.back_to_back.add("".join(self.controls[-3:]))
        self.previous = observation

    def report(self):
        config = self.config
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.width > 1:
            classes.update(("partial_unknown", "mixed_x_z"))
        goals = {
            "all_four_control_states": set(self.states) == set("01xz"),
            "every_pattern_in_both_known_modes": set(product("01", classes)) <= self.patterns,
            "every_input_bit_four_states_in_both_modes": set(product("01", range(config.width), "01xz")) <= self.bit_values,
            "state_cross_stable_and_changing_data": set(product("01xz", (False, True))) <= self.state_activity,
            "control_transition_cross_data_activity": set(product("01xz", "01xz", (False, True))) <= self.transitions,
            "every_transparent_bit_four_state_transition": {
                ("0", bit, before, after) for bit, before, after in product(range(config.width), "01xz", "01xz") if before != after
            } <= self.bit_transitions,
            "every_bit_toggles_both_ways_while_isolated": set(product("1", range(config.width), "01", "01")) - {
                ("1", bit, state, state) for bit, state in product(range(config.width), "01")
            } <= self.bit_transitions,
            "unknown_control_poison_with_equal_different_x_z_data": set(product("xz", range(config.width), ("equal", "different", "x", "z"))) <= self.unknown_relations,
            "known_control_assertions_detect_x_and_z": set(self.control_violations) == set("xz"),
            "back_to_back_assertion_and_release": {"010", "101"} <= self.back_to_back,
            "short_and_long_holds_in_both_known_modes": set(product("01", ("short", "long"))) <= self.holds,
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 8:
            goals["exhaustive_binary_data_in_both_modes"] = set(product("01", (f"{value:0{config.width}b}" for value in range(config.maximum + 1)))) <= self.exhaustive
        if config.width <= 2:
            words = ("".join(word) for word in product("01xz", repeat=config.width))
            goals["exhaustive_four_state_truth_table"] = set(product("01xz", words)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "CLAMP_VALUE": config.clamp_value},
            "clamp_class": config.clamp_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "output_transitions": self.output_transitions, "expected_control_violations": dict(self.control_violations),
            "goals": goals,
            "bins": {"control_states": dict(self.states), "bit_values": sorted(self.bit_values),
                     "pattern_classes": sorted(self.patterns), "state_data_activity": sorted(self.state_activity),
                     "control_transition_data_activity": sorted(self.transitions), "bit_transitions": sorted(self.bit_transitions),
                     "unknown_control_data_relations": sorted(self.unknown_relations), "back_to_back": sorted(self.back_to_back),
                     "hold_classes": sorted(self.holds), "small_truth_table_entries": len(self.exhaustive) if config.width <= 8 else None},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing operand isolation coverage: {missing}"
        self.logger.info("Operand isolation coverage PASS: %d transactions", self.checks)


class OperandIsolationEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = OperandIsolationDriver("driver", self)
        self.monitor = OperandIsolationMonitor("monitor", self)
        self.scoreboard = OperandIsolationScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
