"""PyUVM functional retention model, sampled protocol assertions, and wave checks.

There are no supplies in this portable interface. Save/restore evidence here
must not be presented as UPF, supply-loss, or technology retention signoff.
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


@dataclass(frozen=True)
class RetentionConfig:
    width: int
    reset_value: int
    async_reset: bool
    has_enable: bool
    seed: int
    random_cycles: int
    period_ps: int
    check_image: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> RetentionConfig:
        flags = [os.getenv(name, default) for name, default in (
            ("RETENTION_REGISTER_ASYNC_RESET", "0"), ("RETENTION_REGISTER_HAS_ENABLE", "1"),
            ("RETENTION_REGISTER_CHECK_IMAGE", "1"),
        )]
        assert all(flag in ("0", "1") for flag in flags), "Static flags must be zero or one"
        period = Decimal(os.getenv("TEST_CLOCK_PERIOD_NS", "4")) * 1000
        assert period.is_finite() and period == int(period) and period >= 32 and int(period) % 4 == 0
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/retention_register/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("RETENTION_REGISTER_WIDTH", str(len(cocotb.top.o_q)))),
            reset_value=int(os.getenv("RETENTION_REGISTER_RESET_VALUE", "0"), 0),
            async_reset=flags[0] == "1", has_enable=flags[1] == "1", check_image=flags[2] == "1",
            seed=int(os.getenv("RETENTION_REGISTER_SEED", "20261011")),
            random_cycles=int(os.getenv("RETENTION_REGISTER_RANDOM_CYCLES", "2000")), period_ps=int(period),
            coverage_file=Path(os.getenv("RETENTION_REGISTER_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and 0 <= config.reset_value <= config.maximum
        assert config.random_cycles >= 1000 and get_time_from_sim_steps(1, unit="ps") <= 1
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use TEST_SETTLE_NS=0 for this zero-delay RTL suite"
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def reset_bits(self) -> str:
        return f"{self.reset_value:0{self.width}b}"

    @property
    def reset_class(self) -> str:
        return "zero" if self.reset_value == 0 else "one" if self.reset_value == self.maximum else "mixed"

    @property
    def patterns(self) -> tuple[str, ...]:
        values = {0, self.maximum, self.reset_value, self.reset_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.width))
        values.update(int((pattern * self.width)[:self.width], 2) for pattern in ("01", "10"))
        words = {f"{value:0{self.width}b}" for value in values}
        words.update(state * self.width for state in "xz")
        if self.width > 1:
            words.update((pattern * self.width)[:self.width] for pattern in ("xz", "zx", "0x", "1z"))
        return tuple(sorted(words))


def bits(value: int | str, width: int) -> str:
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Stimulus does not fit the data port"
        return f"{value:0{width}b}"
    value = value.lower()
    assert len(value) == width and set(value) <= set("01xz"), "Invalid four-state data"
    return value


def logic(handle) -> str:
    return str(handle.value).lower()


@dataclass(frozen=True)
class Inputs:
    clk: int
    rstb: int | str
    enable: int | str
    save: int | str
    restore: int | str
    data: int | str


def violations(config, inputs, valid_save, previous_command, *, rising=True, async_event=False) -> set[str]:
    """Protocol is checked at sampled events, not at off-edge control activity."""
    reset, enable, save, restore = (str(value).lower() for value in (inputs.rstb, inputs.enable, inputs.save, inputs.restore))
    result = set()
    if (rising or async_event) and reset not in ("0", "1"):
        result.add("unknown_reset")
    if rising:
        for name, value in (("enable", enable), ("save", save), ("restore", restore)):
            if value not in ("0", "1"):
                result.add("unknown_" + name)
        if save == restore == "1":
            result.add("save_restore_conflict")
        if config.has_enable and enable == "1" and (save == "1" or restore == "1"):
            result.add("enable_during_retention")
        if reset == "1":
            if restore == "1" and not valid_save:
                result.add("restore_without_save")
            command = "restore" if restore == "1" else "save" if save == "1" else None
            if command == previous_command and command in ("save", "restore"):
                result.add("repeat_" + command)
    return result


@dataclass(frozen=True)
class State:
    visible: str
    retained: str


def next_state(config: RetentionConfig, state: State, inputs: Inputs) -> tuple[State, str]:
    """Reference the architectural priority table and pre-edge storage values."""
    reset, restore, save, enable = (str(value).lower() for value in (inputs.rstb, inputs.restore, inputs.save, inputs.enable))
    unknown = "x" * config.width
    if reset == "0":
        return State(config.reset_bits, config.reset_bits), "reset"
    if reset != "1" or restore not in ("0", "1") or save not in ("0", "1"):
        return State(unknown, unknown), "unknown"
    requests = {"restore": restore == "1", "save": save == "1",
                "capture": not config.has_enable or enable == "1", "hold": True}
    command = next(name for name in ("restore", "save", "capture", "hold") if requests[name])
    if restore == save == "0" and config.has_enable and enable not in ("0", "1"):
        return State(unknown, state.retained), "unknown"
    outcomes = {
        "restore": State(state.retained, state.retained),
        "save": State(state.visible, state.visible),
        "capture": State(bits(inputs.data, config.width), state.retained), "hold": state,
    }
    return outcomes[command], command


def pattern_classes(word: str) -> set[str]:
    classes = set()
    for state, name in (("0", "zero"), ("1", "one"), ("x", "all_x"), ("z", "all_z")):
        if word == state * len(word):
            classes.add(name)
    if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
        classes.add("alternating")
    if set(word) & {"x", "z"} and set(word) & {"0", "1"}:
        classes.add("partial_unknown")
    if {"x", "z"} <= set(word):
        classes.add("mixed_x_z")
    return classes


class RetentionItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, duration_ps, expected=(), context="running"):
        super().__init__(label)
        assert inputs.clk in (0, 1) and all(str(value).lower() in ("0", "1", "x", "z") for value in (inputs.rstb, inputs.enable, inputs.save, inputs.restore))
        assert duration_ps >= 3 and context in ("running", "stopped")
        self.inputs, self.duration_ps, self.expected, self.context = inputs, duration_ps, frozenset(expected), context


@dataclass(frozen=True)
class Observation:
    time_ps: int
    inputs: Inputs
    visible: str
    retained: str | None
    item: RetentionItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    inputs: Inputs
    allowed: bool


def ports() -> Inputs:
    dut = cocotb.top
    return Inputs(int(logic(dut.i_clk)), logic(dut.i_rstb), logic(dut.i_enable), logic(dut.i_save), logic(dut.i_restore), logic(dut.i_d))


class RetentionDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(3, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            previous = ports()
            reset = str(item.inputs.rstb).lower()
            falling_reset = str(previous.rstb) == "1" and reset in "0xz" or str(previous.rstb) in "xz" and reset == "0"
            self.active.update(item=item, stage="settled", time_ps=int(get_sim_time(unit="ps")),
                               allowed=previous.clk == 0 and item.inputs.clk == 1 or self.config.async_reset and falling_reset)
            for port, value in (("i_clk", item.inputs.clk), ("i_rstb", item.inputs.rstb), ("i_enable", item.inputs.enable),
                                ("i_save", item.inputs.save), ("i_restore", item.inputs.restore)):
                getattr(cocotb.top, port).value = value
            cocotb.top.i_d.value = bits(item.inputs.data, self.config.width)
            await Timer(1, unit="ps")
            self.active["sample"].set()
            await ReadOnly()
            self.active["allowed"] = False
            await Timer(item.duration_ps - 2, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed held sample"
            self.seq_item_port.item_done()


class RetentionMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)
        self.image = getattr(cocotb.top, "retained_image", None) if self.config.check_image else None
        if self.config.check_image:
            assert self.image is not None and len(self.image) == self.config.width, "Portable retained_image is required"

    async def activity(self, signal, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            allowed = self.active["allowed"]
            await ReadOnly()
            value = logic(handle)
            if value != previous:
                self.ap.write(Activity(signal, value, ports(), allowed))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.activity("o_q", cocotb.top.o_q))]
        if self.image is not None:
            tasks.append(cocotb.start_soon(self.activity("retained_image", self.image)))
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                self.ap.write(Observation(self.active["time_ps"], ports(), logic(cocotb.top.o_q),
                                          logic(self.image) if self.image is not None else None,
                                          self.active["item"], self.active["stage"]))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()


class RetentionScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        initial = self.config.reset_bits if self.config.async_reset else "x" * self.config.width
        self.state = State(initial, initial)
        self.previous = None
        self.valid_save = False
        self.previous_command = None
        self.last_save = None
        self.checks = self.held_checks = self.random_checks = self.clocked_checks = 0
        self.command_counts, self.diagnostics, self.activity_counts = Counter(), Counter(), Counter()
        self.priority, self.saved_bits, self.restored_bits, self.saved_classes, self.interval_cross = set(), set(), set(), set(), set()
        self.reset_phases, self.release_phases, self.stopped, self.unknown_controls, self.ignored_enable = set(), set(), set(), set(), set()
        self.latest_save_restores = self.multiple_write_restores = self.legal_restores = 0
        self.writes_since_save = self.saves_before_restore = 0

    def event(self, inputs):
        old = self.previous.inputs if self.previous else Inputs(0, "0", "0", "0", "0", "0" * self.config.width)
        rising = old.clk == 0 and inputs.clk == 1
        negative = str(old.rstb) == "1" and str(inputs.rstb) in "0xz" or str(old.rstb) in "xz" and str(inputs.rstb) == "0"
        return rising, self.config.async_reset and negative

    def predicted(self, inputs):
        rising, asynchronous = self.event(inputs)
        return next_state(self.config, self.state, inputs) if rising or asynchronous else (self.state, None)

    def write(self, observation):
        if isinstance(observation, Activity):
            assert observation.allowed, f"Out-of-event activity changed {observation.signal} to {observation.value}"
            state, _ = self.predicted(observation.inputs)
            expected = state.visible if observation.signal == "o_q" else state.retained
            assert observation.value == expected, f"Event waveform mismatch: {observation.signal}={observation.value}, expected={expected}"
            self.activity_counts[observation.signal] += 1
            return
        config, inputs, item = self.config, observation.inputs, observation.item
        requested = item.inputs
        assert inputs == Inputs(requested.clk, str(requested.rstb).lower(), str(requested.enable).lower(),
                                str(requested.save).lower(), str(requested.restore).lower(), bits(requested.data, config.width)), "Stimulus was coerced"
        if observation.stage == "held":
            self.held_checks += 1
            self.check_outputs(observation)
            return
        rising, asynchronous = self.event(inputs)
        if rising or asynchronous:
            errors = violations(config, inputs, self.valid_save, self.previous_command, rising=rising, async_event=asynchronous)
            try:
                assert not errors, "Protocol assertion failed: " + ",".join(sorted(errors))
            except AssertionError:
                if not errors <= item.expected:
                    raise
                for name in errors:
                    if not self.diagnostics[name]:
                        self.logger.info("Expected protocol assertion: %s", name)
                    self.diagnostics[name] += 1
            if rising:
                assert errors == item.expected, f"Expected protocol diagnostics {sorted(item.expected)}, got {sorted(errors)}"
            prior = self.state
            self.state, command = next_state(config, prior, inputs)
            self.command_counts[command] += 1
            if rising:
                self.clocked_checks += 1
                self.random_checks += observation.item.get_name().startswith("random_cycle_")
                if all(str(value) in ("0", "1") for value in (inputs.rstb, inputs.restore, inputs.save, inputs.enable)):
                    self.priority.add((str(inputs.rstb), str(inputs.restore), str(inputs.save), str(inputs.enable)))
                if not config.has_enable:
                    self.ignored_enable.add(str(inputs.enable))
            if command == "reset" or command == "unknown" and (str(inputs.rstb) != "1" or str(inputs.save) in "xz" or str(inputs.restore) in "xz"):
                self.valid_save, self.last_save = False, None
                self.saves_before_restore = self.writes_since_save = 0
            elif command == "save":
                self.valid_save = True
                self.saves_before_restore += 1
                self.writes_since_save = 0
                classes = pattern_classes(prior.visible)
                if item.get_name().startswith("random_saved_") or item.get_name().startswith("random_cycle_"):
                    classes.add("random")
                self.saved_classes.update(classes)
                self.last_save = observation.time_ps, classes
                if not errors:
                    self.saved_bits.update(enumerate(reversed(prior.visible)))
            elif command == "capture" and self.valid_save:
                self.writes_since_save += 1
            elif command == "restore":
                if self.valid_save and not errors:
                    self.legal_restores += 1
                    self.restored_bits.update(enumerate(reversed(self.state.visible)))
                    self.multiple_write_restores += self.writes_since_save >= 2
                    self.latest_save_restores += self.saves_before_restore >= 2
                    if self.last_save:
                        interval = "long" if observation.time_ps - self.last_save[0] >= 8 * config.period_ps else "short"
                        self.interval_cross.update((name, interval) for name in self.last_save[1])
                self.valid_save = False
                self.saves_before_restore = self.writes_since_save = 0
            self.previous_command = command
            for name in errors:
                if name.startswith("unknown_"):
                    field = {"reset": "rstb", "enable": "enable", "save": "save", "restore": "restore"}[name[8:]]
                    self.unknown_controls.add((name, str(getattr(inputs, field))))
        old = self.previous.inputs if self.previous else None
        if old and str(old.rstb) == "1" and str(inputs.rstb) == "0":
            self.reset_phases.add(inputs.clk)
        if old and str(old.rstb) == "0" and str(inputs.rstb) == "1":
            self.release_phases.add(inputs.clk)
        if item.context == "stopped":
            assert old is not None and old.clk == inputs.clk and item.duration_ps >= 2 * config.period_ps
            self.stopped.add(inputs.clk)
        self.check_outputs(observation)
        self.checks += 1
        self.previous = observation

    def check_outputs(self, observation):
        assert observation.visible == self.state.visible, f"Visible state mismatch: {observation.visible}, expected={self.state.visible}"
        if observation.retained is not None:
            assert observation.retained == self.state.retained, f"Retained image mismatch: {observation.retained}, expected={self.state.retained}"

    def report(self):
        config = self.config
        diagnostic_names = {"unknown_reset", "unknown_enable", "unknown_save", "unknown_restore", "save_restore_conflict",
                            "restore_without_save", "repeat_save", "repeat_restore"}
        if config.has_enable:
            diagnostic_names.add("enable_during_retention")
        classes = {"zero", "one", "alternating", "random", "all_x", "all_z"}
        if config.width > 1:
            classes.update(("mixed_x_z", "partial_unknown"))
        goals = {
            "all_binary_control_priority_combinations": self.priority == set(product("01", repeat=4)),
            "saved_and_restored_every_bit_four_states": self.saved_bits == self.restored_bits == set(product(range(config.width), "01xz")),
            "every_saved_data_class": classes <= self.saved_classes,
            "saved_data_class_short_long_interval_cross": set(product(("zero", "one", "alternating", "random"), ("short", "long"))) <= self.interval_cross,
            "restore_after_multiple_normal_writes": self.multiple_write_restores > 0,
            "restore_of_most_recent_save": self.latest_save_restores > 0,
            "repeated_legal_save_restore_epochs": self.legal_restores >= 16,
            "all_protocol_diagnostics_active": diagnostic_names <= set(self.diagnostics),
            "every_control_x_and_z_sampled": set(product(("unknown_reset", "unknown_enable", "unknown_save", "unknown_restore"), "xz")) <= self.unknown_controls,
            "reset_assertion_and_release_both_phases": self.reset_phases == self.release_phases == {0, 1},
            "stopped_clock_holds_both_storage_images": self.stopped == {0, 1},
            "normal_capture_and_reset": self.command_counts["capture"] > 0 and self.command_counts["reset"] > 0,
            "every_transaction_checked_after_hold": self.checks == self.held_checks,
            "random_clocked_cycles": self.random_checks == config.random_cycles,
        }
        if config.has_enable:
            goals["disabled_functional_hold"] = self.command_counts["hold"] >= 16
        else:
            goals["enable_ignored_for_all_four_values"] = self.ignored_enable == set("01xz")
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "RESET_VALUE": config.reset_value, "ASYNC_RESET": int(config.async_reset), "HAS_ENABLE": int(config.has_enable)},
            "reset_class": config.reset_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "clocked_checks": self.clocked_checks,
            "random_transactions": self.random_checks, "legal_restore_epochs": self.legal_restores,
            "portable_image_assertions": "PASS" if config.check_image else "NOT_RUN", "goals": goals,
            "commands": dict(self.command_counts), "expected_protocol_violations": dict(self.diagnostics),
            "bins": {"control_priority": sorted(self.priority), "saved_bit_values": sorted(self.saved_bits), "restored_bit_values": sorted(self.restored_bits),
                     "saved_data_classes": sorted(self.saved_classes), "saved_class_interval": sorted(self.interval_cross),
                     "reset_assert_clock_phases": sorted(self.reset_phases), "reset_release_clock_phases": sorted(self.release_phases),
                     "stopped_clock_phases": sorted(self.stopped), "unknown_controls": sorted(self.unknown_controls), "ignored_enable": sorted(self.ignored_enable),
                     "output_image_transitions": dict(self.activity_counts)},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing retention register coverage: {missing}"
        self.logger.info("Retention register coverage PASS: %d transactions", self.checks)


class RetentionEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = RetentionDriver("driver", self)
        self.monitor = RetentionMonitor("monitor", self)
        self.scoreboard = RetentionScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
