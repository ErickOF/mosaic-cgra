"""PyUVM decoder components with an independent combinational reference model."""

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
class DecoderConfig:
    num_outputs: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> DecoderConfig:
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/decoder/results.xml")).with_name("coverage.json")
        config = cls(
            num_outputs=int(os.getenv("DECODER_NUM_OUTPUTS", str(len(cocotb.top.o_decoded)))),
            seed=int(os.getenv("DECODER_SEED", "20261010")),
            random_cycles=int(os.getenv("DECODER_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("DECODER_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.num_outputs >= 1
        assert config.random_cycles >= 1000, "Use at least 1000 randomized transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def select_width(self) -> int:
        return max(1, (self.num_outputs - 1).bit_length())

    @property
    def encodings(self) -> range:
        return range(1 << self.select_width)

    @property
    def invalid_encodings(self) -> range:
        return range(self.num_outputs, 1 << self.select_width)

    @property
    def sample_ns(self) -> float:
        # Advance one picosecond before ReadOnly for zero-delay RTL; callers
        # may request a larger settling interval for a separate timed flow.
        return max(0.001, self.settle_ns)


@dataclass(frozen=True)
class Inputs:
    enable: int | str
    select: int | str

    def select_bits(self, width: int) -> str:
        if isinstance(self.select, int):
            assert 0 <= self.select < 1 << width, "Do not truncate input encodings"
            return f"{self.select:0{width}b}"
        assert len(self.select) == width and set(self.select.lower()) <= set("01xz")
        return self.select.lower()


def expected_outputs(num_outputs: int, enable: str, select: str) -> tuple[int, int]:
    """Decode known, enabled, in-range inputs; everything else fails closed."""
    if enable != "1" or set(select) - {"0", "1"}:
        return 0, 0
    selected = int(select, 2)
    return (1 << selected, 1) if selected < num_outputs else (0, 0)


class DecoderItem(uvm_sequence_item):
    def __init__(self, label, inputs):
        super().__init__(label)
        self.inputs = inputs


@dataclass(frozen=True)
class Observation:
    label: str
    enable: str
    select: str
    decoded: str
    valid: str
    requested: Inputs
    continuously_disabled: bool


@dataclass(frozen=True)
class OutputActivity:
    signal: str
    value: str
    continuously_disabled: bool


class DecoderDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            # Move out of the previous transaction's ReadOnly phase.
            await Timer(1, unit="ps")
            self.active["item"] = item
            self.active["quiet"] = str(self.dut.i_enable.value) == "0" and item.inputs.enable == 0
            self.dut.i_enable.value = item.inputs.enable
            self.dut.i_select.value = item.inputs.select_bits(self.config.select_width)
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            # Let the passive monitor finish before the sequence can end.
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "The monitor did not consume the sample"
            self.seq_item_port.item_done()


class DecoderMonitor(uvm_monitor):
    """Read actual ports and monitor activity throughout disabled intervals."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self, signal):
        handle = getattr(self.dut, signal)
        while True:
            await handle.value_change
            # Re-arm immediately, preserving observable transients that
            # could disappear before a settled combinational sample.
            self.ap.write(OutputActivity(signal, str(handle.value).lower(), self.active["quiet"]))

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.output_activity(name)) for name in ("o_decoded", "o_select_valid")]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(self.dut.i_enable.value).lower(),
                    str(self.dut.i_select.value).lower(), str(self.dut.o_decoded.value).lower(),
                    str(self.dut.o_select_valid.value).lower(), item.inputs, self.active["quiet"],
                ))
                # Consume each notification once, even if two identical input
                # transactions produce no HDL value-change callbacks.
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()


class DecoderScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.checks = 0
        self.random_checks = 0
        self.legal = set()
        self.invalid = set()
        self.disabled = set()
        self.disabled_quiet = set()
        self.activated = set()
        self.legal_pairs = set()
        self.legal_to_invalid = set()
        self.invalid_to_legal = set()
        self.enable_transitions = set()
        self.simultaneous = set()
        self.unknown_enable = set()
        self.unknown_select = set()
        self.full_unknown_select = set()
        self.mixed_unknown_select = set()
        self.activity = Counter()

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.continuously_disabled, (
                f"Disabled selection activity changed {observation.signal} to {observation.value}"
            )
            assert not set(observation.value) - {"0", "1"}, "An output became unknown"
            if observation.signal == "o_decoded":
                value = int(observation.value, 2)
                assert value & (value - 1) == 0, "A transient decoded value was multi-hot"
            self.activity[observation.signal] += 1
            return
        assert isinstance(observation, Observation)
        config = self.config
        assert observation.enable == str(observation.requested.enable).lower(), "Enable stimulus was resolved or changed"
        assert observation.select == observation.requested.select_bits(config.select_width), "Selection stimulus was resolved or changed"
        assert not (set(observation.decoded + observation.valid) - {"0", "1"}), "Outputs must always be known"
        decoded, valid = int(observation.decoded, 2), int(observation.valid, 2)
        expected = expected_outputs(config.num_outputs, observation.enable, observation.select)
        assert (decoded, valid) == expected, (
            f"{observation.label}: enable={observation.enable}, select={observation.select}; "
            f"outputs={(decoded, valid)}, expected={expected}"
        )
        assert decoded & (decoded - 1) == 0, "o_decoded must be one-hot or zero"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        selected = int(observation.select, 2) if set(observation.select) <= {"0", "1"} else None
        if selected is not None:
            if observation.enable == "0":
                self.disabled.add(selected)
                if observation.continuously_disabled:
                    self.disabled_quiet.add(selected)
            elif observation.enable == "1":
                (self.legal if selected < config.num_outputs else self.invalid).add(selected)
            else:
                self.unknown_enable.add((observation.enable, selected))
        else:
            for index, value in enumerate(reversed(observation.select)):
                if value in ("x", "z"):
                    self.unknown_select.add((index, value, observation.enable))
            if len(set(observation.select)) == 1:
                self.full_unknown_select.add((observation.select[0], observation.enable))
            if {"x", "z"} <= set(observation.select):
                self.mixed_unknown_select.add(observation.enable)
        if decoded:
            self.activated.add(decoded.bit_length() - 1)
        previous = self.previous
        if previous is not None:
            before = int(previous.select, 2) if set(previous.select) <= {"0", "1"} else None
            if before is not None and selected is not None:
                if previous.enable == observation.enable == "1":
                    if before < config.num_outputs and selected < config.num_outputs:
                        self.legal_pairs.add((before, selected))
                    elif before < config.num_outputs:
                        self.legal_to_invalid.add((before, selected))
                    elif selected < config.num_outputs:
                        self.invalid_to_legal.add((before, selected))
                if previous.enable in ("0", "1") and observation.enable in ("0", "1") and previous.enable != observation.enable:
                    if before == selected:
                        self.enable_transitions.add((selected, observation.enable))
                    else:
                        self.simultaneous.add(observation.enable)
        self.previous = observation

    def report(self):
        config = self.config
        goals = {
            "every_legal_selection": set(range(config.num_outputs)) <= self.legal,
            "every_invalid_encoding": set(config.invalid_encodings) <= self.invalid,
            "disabled_every_encoding": set(config.encodings) <= self.disabled,
            "disabled_selection_no_activity": set(config.encodings) <= self.disabled_quiet,
            "all_legal_pairs": set(product(range(config.num_outputs), repeat=2)) <= self.legal_pairs,
            "all_legal_to_invalid_pairs": set(product(range(config.num_outputs), config.invalid_encodings)) <= self.legal_to_invalid,
            "all_invalid_to_legal_pairs": set(product(config.invalid_encodings, range(config.num_outputs))) <= self.invalid_to_legal,
            "enable_assert_deassert_every_encoding": set(product(config.encodings, ("0", "1"))) <= self.enable_transitions,
            "simultaneous_enable_and_selection": self.simultaneous == {"0", "1"},
            "every_output_bit": set(range(config.num_outputs)) <= self.activated,
            "unknown_enable_every_encoding": set(product(("x", "z"), config.encodings)) <= self.unknown_enable,
            "unknown_select_every_bit": set(product(range(config.select_width), ("x", "z"), ("0", "1"))) <= self.unknown_select,
            "all_x_all_z_selections": set(product(("x", "z"), ("0", "1"))) <= self.full_unknown_select,
            "random_activity": self.random_checks >= config.random_cycles,
        }
        if config.select_width > 1:
            goals["mixed_x_z_selections"] = self.mixed_unknown_select == {"0", "1"}
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"NUM_OUTPUTS": config.num_outputs, "SELECT_WIDTH": config.select_width},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "random_transactions": self.random_checks,
            "output_activity": dict(self.activity), "goals": goals,
            "legal_selection_coverage_percent": 100 * len(self.legal) / config.num_outputs,
            "invalid_encoding_coverage_percent": 100 * len(self.invalid) / len(config.invalid_encodings) if config.invalid_encodings else None,
            "invalid_encoding_coverage_applicable": bool(config.invalid_encodings),
            "legal_pair_coverage_percent": 100 * len(self.legal_pairs) / config.num_outputs ** 2,
            "bins": {
                "legal_selections": sorted(self.legal), "invalid_encodings": sorted(self.invalid),
                "disabled_selections": sorted(self.disabled), "disabled_quiet_selections": sorted(self.disabled_quiet),
                "activated_output_bits": sorted(self.activated), "legal_pairs": sorted(self.legal_pairs),
                "legal_to_invalid_pairs": sorted(self.legal_to_invalid), "invalid_to_legal_pairs": sorted(self.invalid_to_legal),
                "enable_transitions": sorted(self.enable_transitions),
                "unknown_enable": sorted(self.unknown_enable), "unknown_select": sorted(self.unknown_select),
                "all_unknown_select": sorted(self.full_unknown_select),
                "mixed_unknown_select_enable": sorted(self.mixed_unknown_select),
            },
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing decoder coverage: {missing}"
        self.logger.info("Decoder coverage PASS: %d transactions, %d legal pairs",
                         self.checks, len(self.legal_pairs))


class DecoderEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = DecoderDriver("driver", self)
        self.monitor = DecoderMonitor("monitor", self)
        self.scoreboard = DecoderScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
