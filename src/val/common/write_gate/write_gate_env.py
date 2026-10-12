"""PyUVM port checks and destination-state comparisons for write gating.

The gate reference is a per-bit four-state truth table. Integration uses real
HDL destinations and an independent ungated state model; event counts describe
write activity and do not estimate physical power or energy.
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

# Explicit rows distinguish masked unknowns from illegal requested writes.
TRUTH = {
    ("0", "0"): ("0", "0"), ("0", "1"): ("0", "0"),
    ("0", "x"): ("0", "0"), ("0", "z"): ("0", "0"),
    ("1", "0"): ("1", "0"), ("1", "1"): ("0", "1"),
    ("1", "x"): ("x", "x"), ("1", "z"): ("x", "x"),
    ("x", "0"): ("x", "0"), ("x", "1"): ("0", "x"),
    ("x", "x"): ("x", "x"), ("x", "z"): ("x", "x"),
    ("z", "0"): ("x", "0"), ("z", "1"): ("0", "x"),
    ("z", "x"): ("x", "x"), ("z", "z"): ("x", "x"),
}


def bits(value: int | str, width: int) -> str:
    """Preserve X/Z and reject accidental stimulus truncation."""
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Stimulus does not fit the port"
        return f"{value:0{width}b}"
    word = value.lower()
    assert len(word) == width and set(word) <= set("01xz"), "Invalid four-state stimulus"
    return word


def control_violations(write: str, suppress: str) -> set[str]:
    violations = set()
    if set(write) & set("xz"):
        violations.add("unknown_write_enable")
    if any(w != "0" and s in "xz" for w, s in zip(write, suppress, strict=True)):
        violations.add("unknown_requested_suppression")
    return violations


def mask_class(word: str) -> str:
    if word == "0" * len(word):
        return "zero"
    if word == "1" * len(word):
        return "one"
    if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
        return "alternating"
    return "other" if set(word) <= set("01") else "unknown"


def decision(write: str, suppress: str) -> str:
    if set(write + suppress) - set("01"):
        return "unknown"
    requested = write.count("1")
    blocked = sum(w == s == "1" for w, s in zip(write, suppress, strict=True))
    return "no_request" if not requested else "permitted" if not blocked else "suppressed" if blocked == requested else "mixed"


@dataclass(frozen=True)
class WriteGateConfig:
    width: int
    integration: bool
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> WriteGateConfig:
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/write_gate/results.xml")).with_name("coverage.json")
        mode = os.getenv("WRITE_GATE_INTEGRATION", "0")
        assert mode in ("0", "1"), "WRITE_GATE_INTEGRATION must be 0 or 1"
        config = cls(
            int(os.getenv("WRITE_GATE_WIDTH", str(len(cocotb.top.o_write_enable)))),
            mode == "1", int(os.getenv("WRITE_GATE_SEED", "20261011")),
            int(os.getenv("WRITE_GATE_RANDOM_CYCLES", "2000")),
            float(os.getenv("TEST_SETTLE_NS", "0")),
            Path(os.getenv("WRITE_GATE_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        assert config.integration == hasattr(cocotb.top, "i_clk"), "Wrong fixture for integration mode"
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)


@dataclass(frozen=True)
class Inputs:
    write: int | str
    suppress: int | str
    data: int = 0
    destination: str = "register"
    address: int = 0
    protocol: str = "accepted"
    reason: str = "none"


class WriteGateItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, expected_violations=(), hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.inputs = inputs
        self.expected_violations = set(expected_violations)
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    item: WriteGateItem
    stage: str
    write: str
    suppress: str
    permitted: str
    suppressed: str
    data: str | None
    destination: int | None
    address: int | None
    valid: int | None
    register: str | None
    memory: str | None


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    quiet: bool
    capture_window: bool


class WriteGateDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def sample(self, stage):
        assert not self.active["sample"].is_set(), "Monitor missed a sample"
        self.active["stage"] = stage
        self.active["sample"].set()
        await ReadOnly()

    async def run_phase(self):
        await Timer(5, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            write, suppress = bits(item.inputs.write, self.config.width), bits(item.inputs.suppress, self.config.width)
            unchanged = (write == str(cocotb.top.i_write_enable.value).lower()
                         and suppress == str(cocotb.top.i_suppress.value).lower())
            self.active.update(item=item, quiet=unchanged, capture_window=False)
            cocotb.top.i_write_enable.value = write
            cocotb.top.i_suppress.value = suppress
            if self.config.integration:
                inputs = item.inputs
                assert inputs.destination in ("register", "memory") and 0 <= inputs.address < 4
                cocotb.top.i_write_data.value = bits(inputs.data, self.config.width)
                cocotb.top.i_destination.value = inputs.destination == "memory"
                cocotb.top.i_address.value = inputs.address
                cocotb.top.i_capture_valid.value = inputs.protocol == "accepted"
            await Timer(self.config.sample_ns, unit="ns")
            await self.sample("settled")
            self.active["quiet"] = True
            if self.config.integration:
                await Timer(1, unit="ps")
                self.active["capture_window"] = True
                cocotb.top.i_clk.value = 1
                await Timer(1, unit="ps")
                await self.sample("captured")
                self.active["capture_window"] = False
            await Timer(item.hold_ns, unit="ns")
            await self.sample("held")
            await Timer(1, unit="ps")
            if self.config.integration:
                cocotb.top.i_clk.value = 0
                await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()


class WriteGateMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def activity(self, name):
        signal = getattr(cocotb.top, name)
        previous = str(signal.value).lower()
        while True:
            await signal.value_change
            quiet, capture = self.active["quiet"], self.active["capture_window"]
            await ReadOnly()
            value = str(signal.value).lower()
            if value != previous:
                self.ap.write(Activity(name, value, quiet, capture))
                previous = value

    async def run_phase(self):
        await Timer(4, unit="ps")
        await ReadOnly()
        signals = ["o_write_enable", "o_write_suppressed"]
        if self.config.integration:
            signals += ["o_register_state", "o_memory_state"]
        tasks = [cocotb.start_soon(self.activity(name)) for name in signals]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                extra = (
                    str(cocotb.top.i_write_data.value).lower(), int(cocotb.top.i_destination.value),
                    int(cocotb.top.i_address.value), int(cocotb.top.i_capture_valid.value),
                    str(cocotb.top.o_register_state.value).lower(), str(cocotb.top.o_memory_state.value).lower(),
                ) if self.config.integration else (None,) * 6
                self.ap.write(Observation(
                    self.active["item"], self.active["stage"],
                    str(cocotb.top.i_write_enable.value).lower(), str(cocotb.top.i_suppress.value).lower(),
                    str(cocotb.top.o_write_enable.value).lower(), str(cocotb.top.o_write_suppressed.value).lower(),
                    *extra,
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()


class WriteGateScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.checks = self.held_checks = self.random_checks = self.capture_checks = 0
        self.output_transitions = 0
        self.bit_states, self.bit_transitions, self.pattern_cross = set(), set(), set()
        self.populations, self.holds, self.exhaustive, self.simultaneous = set(), set(), set(), set()
        self.violations, self.integration_cross = Counter(), set()
        self.previous = None
        self.register = "0" * self.config.width
        self.memory = [self.register] * 4
        self.pending = None
        self.activity_counts = {
            dest: dict(baseline_writes=0, gated_writes=0, baseline_state_toggles=0, gated_state_toggles=0)
            for dest in ("register", "memory")
        }
        self.addresses = set()

    def write(self, observation):
        if isinstance(observation, Activity):
            if observation.signal in ("o_write_enable", "o_write_suppressed"):
                assert not observation.quiet, f"Stable controls changed {observation.signal} to {observation.value}"
                self.output_transitions += 1
            else:
                assert observation.capture_window and self.pending is not None, f"Destination changed outside capture: {observation.signal}"
                register, memory = self.pending
                expected = register if observation.signal == "o_register_state" else "".join(reversed(memory))
                assert observation.value == expected, f"Destination waveform mismatch: {observation.signal}"
            return
        item, config = observation.item, self.config
        assert observation.write == bits(item.inputs.write, config.width), "Write stimulus was coerced"
        assert observation.suppress == bits(item.inputs.suppress, config.width), "Suppression stimulus was coerced"
        violations = control_violations(observation.write, observation.suppress)
        try:
            assert not violations, f"Known-control assertion failed: {','.join(sorted(violations))}"
        except AssertionError:
            if violations != item.expected_violations:
                raise
            if observation.stage == "settled":
                self.violations.update(violations)
        else:
            assert not item.expected_violations, "Expected an illegal control but received legal controls"
        expected = [TRUTH[w, s] for w, s in zip(observation.write, observation.suppress, strict=True)]
        assert observation.permitted == "".join(row[0] for row in expected), f"Permitted-write mismatch: {item.get_name()}/{observation.stage}"
        assert observation.suppressed == "".join(row[1] for row in expected), f"Suppressed-write mismatch: {item.get_name()}/{observation.stage}"
        for w, s, p, b in zip(observation.write, observation.suppress, observation.permitted, observation.suppressed, strict=True):
            if w in "01" and s in "01":
                assert not (p == b == "1"), "Mutual-exclusion assertion failed"
                assert (p == "1" or b == "1") == (w == "1"), "Request-partition assertion failed"
        if config.integration:
            self.check_destination(observation)
        if observation.stage == "held":
            self.held_checks += 1
            self.holds.add((decision(observation.write, observation.suppress), "long" if item.hold_ns >= 1 else "short"))
            return
        if observation.stage == "captured":
            self.capture_checks += 1
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += item.get_name().startswith("random_")
        self.bit_states.update((bit, w, s) for bit, (w, s) in enumerate(zip(reversed(observation.write), reversed(observation.suppress), strict=True)))
        if set(observation.write + observation.suppress) <= set("01"):
            self.pattern_cross.add((mask_class(observation.write), mask_class(observation.suppress)))
            self.populations.add(sum(w == s == "1" for w, s in zip(observation.write, observation.suppress, strict=True)))
        if config.width <= 4:
            self.exhaustive.add((observation.write, observation.suppress))
        if self.previous:
            old = self.previous
            self.simultaneous.add((old.write != observation.write, old.suppress != observation.suppress))
            self.bit_transitions.update(
                (bit, ow, os_, nw, ns) for bit, (ow, os_, nw, ns) in enumerate(zip(
                    reversed(old.write), reversed(old.suppress), reversed(observation.write), reversed(observation.suppress), strict=True))
            )
        self.previous = observation

    def check_destination(self, observation):
        """Compare all HDL state against ungated writes, including untouched words."""
        inputs = observation.item.inputs
        assert not control_violations(observation.write, observation.suppress), "Illegal controls cannot reach destination capture"
        assert observation.data == bits(inputs.data, self.config.width), "Data stimulus was coerced"
        assert observation.destination == (inputs.destination == "memory") and observation.address == inputs.address
        assert inputs.protocol in ("idle", "accepted", "cancelled")
        assert observation.valid == (inputs.protocol == "accepted")
        assert inputs.reason in ("none", "redundant_value", "inactive_destination")
        if inputs.protocol == "idle":
            assert observation.write.count("1") == 0
        if inputs.reason == "none":
            assert observation.suppress.count("1") == 0
        if inputs.reason == "inactive_destination":
            assert inputs.protocol == "cancelled", "Inactive destination must cancel before acceptance"
        if observation.stage == "settled":
            prior = self.register if inputs.destination == "register" else self.memory[inputs.address]
            assert not observation.valid or all(
                not (w == s == "1" and d != q)
                for w, s, d, q in zip(observation.write, observation.suppress, observation.data, prior, strict=True)
            ), "Integration safety assertion failed: suppressed architecturally required write"
            next_word = "".join(
                d if observation.valid and w == "1" else q
                for w, d, q in zip(observation.write, observation.data, prior, strict=True)
            )
            memory = self.memory.copy()
            register = self.register
            if inputs.destination == "register":
                register = next_word
            else:
                memory[inputs.address] = next_word
            self.pending = register, memory
            self.integration_cross.add((inputs.destination, inputs.reason, inputs.protocol, decision(observation.write, observation.suppress)))
            if inputs.destination == "memory" and observation.valid:
                self.addresses.add(inputs.address)
        elif observation.stage == "captured":
            assert self.pending is not None
            previous = self.register if inputs.destination == "register" else self.memory[inputs.address]
            counts = self.activity_counts[inputs.destination]
            counts["baseline_writes"] += observation.write.count("1") if observation.valid else 0
            counts["gated_writes"] += observation.permitted.count("1") if observation.valid else 0
            register, memory = self.pending
            expected = register if inputs.destination == "register" else memory[inputs.address]
            actual = observation.register if inputs.destination == "register" else observation.memory[
                (3 - inputs.address) * self.config.width:(4 - inputs.address) * self.config.width
            ]
            counts["baseline_state_toggles"] += sum(a != b for a, b in zip(previous, expected, strict=True))
            counts["gated_state_toggles"] += sum(a != b for a, b in zip(previous, actual, strict=True))
            self.register, self.memory = register, memory
        assert observation.register == self.register, "Register state differs from ungated reference"
        assert observation.memory == "".join(reversed(self.memory)), "Memory state differs from ungated reference"

    def report(self):
        config = self.config
        classes = {"zero", "one"} | ({"alternating"} if config.width > 1 else set()) | ({"other"} if config.width > 2 else set())
        goals = {
            "every_bit_binary_truth_table": set(product(range(config.width), "01", "01")) <= self.bit_states,
            "held_check_for_every_transaction": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.integration:
            goals.update(
                destination_capture_for_every_transaction=self.capture_checks == self.checks,
                all_memory_addresses=self.addresses == set(range(4)),
                destination_reason_cross=all(any(row[:2] == (dest, reason) for row in self.integration_cross)
                                             for dest, reason in product(("register", "memory"), ("none", "redundant_value", "inactive_destination"))),
                protocol_suppression_cross=all(any(row[0] == dest and row[2:] == (protocol, mode) for row in self.integration_cross)
                                              for dest, protocol, mode in product(("register", "memory"), ("accepted", "cancelled"),
                                                                                 ("permitted", "suppressed", "mixed") if config.width > 1 else ("permitted", "suppressed"))),
                idle_destinations=all(any(row[0] == dest and row[2:] == ("idle", "no_request") for row in self.integration_cross) for dest in ("register", "memory")),
                destination_write_event_reduction=all(0 < row["gated_writes"] < row["baseline_writes"] for row in self.activity_counts.values()),
                unchanged_architectural_state_activity=all(row["baseline_state_toggles"] == row["gated_state_toggles"] for row in self.activity_counts.values()),
            )
        else:
            goals.update(
                every_bit_four_state_truth_table=set(product(range(config.width), "01xz", "01xz")) <= self.bit_states,
                every_bit_binary_control_transition=set(product(range(config.width), "01", "01", "01", "01")) <= self.bit_transitions,
                write_pattern_suppression_pattern_cross=set(product(classes, repeat=2)) <= self.pattern_cross,
                all_suppression_populations=self.populations == set(range(config.width + 1)),
                simultaneous_and_independent_changes=set(product((False, True), repeat=2)) <= self.simultaneous,
                unknown_control_assertions_active=set(self.violations) == {"unknown_write_enable", "unknown_requested_suppression"},
                short_and_long_idle_permitted_suppressed_holds=set(product(("no_request", "permitted", "suppressed"), ("short", "long"))) <= self.holds,
            )
            if config.width <= 4:
                words = [f"{value:0{config.width}b}" for value in range(1 << config.width)]
                goals["exhaustive_binary_masks"] = set(product(words, repeat=2)) <= self.exhaustive
            if config.width <= 2:
                words = ["".join(word) for word in product("01xz", repeat=config.width)]
                goals["exhaustive_four_state_masks"] = set(product(words, repeat=2)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL", "parameters": {"WIDTH": config.width},
            "integration": config.integration, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks,
            "random_transactions": self.random_checks, "destination_captures": self.capture_checks,
            "output_transitions": self.output_transitions, "expected_control_violations": dict(self.violations),
            "destination_activity": self.activity_counts if config.integration else None, "goals": goals,
            "bins": dict(bit_states=sorted(self.bit_states), bit_transitions=sorted(self.bit_transitions),
                         pattern_cross=sorted(self.pattern_cross), suppressed_populations=sorted(self.populations),
                         holds=sorted(self.holds), simultaneous_changes=sorted(self.simultaneous),
                         integration_cross=sorted(self.integration_cross), memory_addresses=sorted(self.addresses)),
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, passed in report["goals"].items() if not passed]
        assert not missing, f"Missing write gate coverage: {missing}"
        self.logger.info("Write gate coverage PASS: %d transactions", self.checks)


class WriteGateEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = WriteGateDriver("driver", self)
        self.monitor = WriteGateMonitor("monitor", self)
        self.scoreboard = WriteGateScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
