"""Four-state PyUVM checks of the portable, powered level-shifter contract."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
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
class LevelShifterConfig:
    width: int
    direction: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> LevelShifterConfig:
        default_report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/level_shifter/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("LEVEL_SHIFTER_WIDTH", str(len(cocotb.top.o_data)))),
            direction=int(os.getenv("LEVEL_SHIFTER_DIRECTION", "0")),
            seed=int(os.getenv("LEVEL_SHIFTER_SEED", "20261011")),
            random_cycles=int(os.getenv("LEVEL_SHIFTER_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("LEVEL_SHIFTER_COVERAGE_FILE", str(default_report))),
        )
        assert config.width >= 1, "WIDTH must be positive"
        assert config.direction in (0, 1), "Direction must be a static zero or one"
        assert config.random_cycles >= 1000, "Use at least 1000 randomized transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    @property
    def patterns(self) -> tuple[str, ...]:
        """Uniform, independent-bit, alternating, and mixed four-state words."""
        values = {0, self.maximum}
        values.update(1 << bit for bit in range(self.width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.width))
        values.update(int((pattern * self.width)[:self.width], 2) for pattern in ("01", "10"))
        patterns = {f"{value:0{self.width}b}" for value in values}
        patterns.update(value * self.width for value in ("x", "z"))
        for bit, state, background in product(range(self.width), "xz", "01"):
            word = [background] * self.width
            word[self.width - bit - 1] = state
            patterns.add("".join(word))
        if self.width > 1:
            patterns.update((word * self.width)[:self.width] for word in ("xz", "zx", "0x", "1z"))
        return tuple(sorted(patterns))


def data_bits(value: int | str, width: int) -> str:
    """Preserve each four-state bit and reject implicit stimulus truncation."""
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Source data does not fit the port"
        return f"{value:0{width}b}"
    result = value.lower()
    assert len(result) == width and set(result) <= set("01xz"), "Invalid four-state data"
    return result


def expected_data(source: str) -> str:
    """Apply the specification's identity truth table independently to each bit."""
    table = {"0": "0", "1": "1", "x": "x", "z": "z"}
    return "".join(table[bit] for bit in source)


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
        if set(word) == {"0", "1"}:
            classes.add("mixed_known")
    if set(word) & {"x", "z"} and set(word) & {"0", "1"}:
        classes.add("mixed_unknown_known")
    if {"x", "z"} <= set(word):
        classes.add("mixed_x_z")
    return classes


class LevelShifterItem(uvm_sequence_item):
    def __init__(self, label, data, *, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.data = data
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    source: str
    output: str
    requested: str
    stage: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    value: str
    stable_input: bool


class LevelShifterDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            self.active.update(item=item, stable=False, stage="settled")
            cocotb.top.i_data.value = data_bits(item.data, self.config.width)
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            # Physical propagation may occur before the settling point. Once
            # settled, unchanged inputs must not create output activity/state.
            self.active["stable"] = True
            await Timer(item.hold_ns, unit="ns")
            assert not self.active["sample"].is_set(), "Monitor missed the settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()


class LevelShifterMonitor(uvm_monitor):
    """Sample actual ports and observe output changes throughout stable intervals."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self):
        while True:
            await cocotb.top.o_data.value_change
            # Re-arm immediately so a transient cannot hide before ReadOnly.
            self.ap.write(OutputActivity(str(cocotb.top.o_data.value).lower(), self.active["stable"]))

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
                    item.get_name(), str(cocotb.top.i_data.value).lower(), str(cocotb.top.o_data.value).lower(),
                    data_bits(item.data, self.config.width), self.active["stage"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            output_task.cancel()


class LevelShifterScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.checks = self.held_checks = self.random_checks = self.output_transitions = 0
        self.bit_values = set()
        self.bit_transitions = set()
        self.classes = Counter()
        self.hold_classes = set()
        self.words = set()
        self.stimulus_hash = hashlib.sha256()

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.stable_input, (
                f"Output changed with stable source data: {observation.value}"
            )
            self.output_transitions += 1
            return
        assert isinstance(observation, Observation)
        assert observation.source == observation.requested, f"{observation.label}: source data was coerced"
        expected = expected_data(observation.source)
        assert observation.output == expected, (
            f"{observation.label}/{observation.stage}: source={observation.source}, "
            f"output={observation.output}, expected={expected}"
        )
        if observation.stage == "held":
            self.held_checks += 1
            self.hold_classes.add("long" if observation.hold_ns >= 1 else "short")
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        self.bit_values.update(enumerate(reversed(observation.output)))
        self.classes.update(pattern_classes(observation.source))
        if self.config.width <= 8:
            self.words.add(observation.source)
        self.stimulus_hash.update(f"{observation.label}:{observation.source}:{observation.hold_ns}\n".encode("ascii"))
        previous = self.previous
        if previous is not None:
            changed = [bit for bit, (before, after) in enumerate(zip(reversed(previous), reversed(observation.source), strict=True)) if before != after]
            if len(changed) <= 1:
                # Require an isolated bit change on each known background.
                # Repeated words cover diagonal state-to-same-state transitions.
                for bit, (before, after) in enumerate(zip(reversed(previous), reversed(observation.source), strict=True)):
                    if changed and bit != changed[0]:
                        continue
                    offset = self.config.width - bit - 1
                    others = observation.source[:offset] + observation.source[offset + 1:]
                    for background in "01":
                        if all(value == background for value in others):
                            self.bit_transitions.add((bit, background, before, after))
        self.previous = observation.source

    def report(self):
        config = self.config
        required_classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.width > 1:
            required_classes.update(("mixed_known", "mixed_unknown_known", "mixed_x_z"))
        goals = {
            "every_bit_preserves_all_four_states": self.bit_values == set(product(range(config.width), "01xz")),
            "every_bit_four_state_transition_on_both_backgrounds": self.bit_transitions == set(product(range(config.width), "01", "01xz", "01xz")),
            "all_data_pattern_classes": required_classes <= set(self.classes),
            "short_and_long_stable_intervals": self.hold_classes == {"short", "long"},
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 8:
            goals["exhaustive_binary_data"] = {f"{value:0{config.width}b}" for value in range(config.maximum + 1)} <= self.words
        if config.width <= 4:
            goals["exhaustive_four_state_data"] = {"".join(word) for word in product("01xz", repeat=config.width)} <= self.words
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "DIRECTION": config.direction},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks,
            "random_transactions": self.random_checks, "output_transitions": self.output_transitions,
            "stimulus_sha256": self.stimulus_hash.hexdigest(), "goals": goals,
            "four_state_bit_coverage_percent": 100 * len(self.bit_values) / (4 * config.width),
            "bins": {"bit_values": sorted(self.bit_values), "independent_bit_transitions": sorted(self.bit_transitions),
                     "pattern_classes": dict(self.classes), "hold_classes": sorted(self.hold_classes),
                     "unique_small_width_words": len(self.words)},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing level shifter coverage: {missing}"
        self.logger.info("Level shifter coverage PASS: %d transactions and %d held checks", self.checks, self.held_checks)


class LevelShifterEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = LevelShifterDriver("driver", self)
        self.monitor = LevelShifterMonitor("monitor", self)
        self.scoreboard = LevelShifterScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
