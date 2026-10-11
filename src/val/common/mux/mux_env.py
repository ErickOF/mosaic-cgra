"""Port-only four-state PyUVM verification of the MOSAIC mux contract."""

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
class MuxConfig:
    num_inputs: int
    data_width: int
    default_value: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> MuxConfig:
        width = len(cocotb.top.o_data)
        default_report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/mux/results.xml")).with_name("coverage.json")
        config = cls(
            num_inputs=int(os.getenv("MUX_NUM_INPUTS", str(len(cocotb.top.i_data) // width))),
            data_width=int(os.getenv("MUX_DATA_WIDTH", str(width))),
            default_value=int(os.getenv("MUX_DEFAULT_VALUE", "0"), 0),
            seed=int(os.getenv("MUX_SEED", "20261011")),
            random_cycles=int(os.getenv("MUX_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("MUX_COVERAGE_FILE", str(default_report))),
        )
        assert config.num_inputs >= 1 and config.data_width >= 1
        assert 0 <= config.default_value <= config.maximum, "Default must fit the data port"
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def select_width(self) -> int:
        return max(1, (self.num_inputs - 1).bit_length())

    @property
    def maximum(self) -> int:
        return (1 << self.data_width) - 1

    @property
    def default_bits(self) -> str:
        return f"{self.default_value:0{self.data_width}b}"

    @property
    def default_class(self) -> str:
        return "zero" if self.default_value == 0 else "one" if self.default_value == self.maximum else "mixed"

    @property
    def invalid_encodings(self) -> range:
        return range(self.num_inputs, 1 << self.select_width)

    @property
    def unknown_selects(self) -> tuple[str, ...]:
        return tuple(word for values in product("01xz", repeat=self.select_width)
                     if set(word := "".join(values)) & {"x", "z"})

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    @property
    def patterns(self) -> tuple[str, ...]:
        values = {0, self.maximum, self.default_value, self.default_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.data_width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.data_width))
        values.update(int((pattern * self.data_width)[:self.data_width], 2) for pattern in ("01", "10"))
        patterns = {f"{value:0{self.data_width}b}" for value in values}
        patterns.update(state * self.data_width for state in "xz")
        for bit, state, background in product(range(self.data_width), "xz", "01"):
            word = [background] * self.data_width
            word[self.data_width - bit - 1] = state
            patterns.add("".join(word))
        if self.data_width > 1:
            patterns.update((word * self.data_width)[:self.data_width] for word in ("xz", "zx"))
        return tuple(sorted(patterns))


def bits(value: int | str, width: int) -> str:
    """Preserve X/Z and reject truncation of data words or selection encodings."""
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Stimulus does not fit the port"
        return f"{value:0{width}b}"
    result = value.lower()
    assert len(result) == width and set(result) <= set("01xz"), "Invalid four-state stimulus"
    return result


def input_words(packed: str, width: int) -> tuple[str, ...]:
    """The rightmost packed word is input zero; preserve each word's bit order."""
    assert len(packed) % width == 0
    return tuple(reversed(tuple(packed[offset:offset + width] for offset in range(0, len(packed), width))))


def expected_outputs(config: MuxConfig, packed: str, select: str) -> tuple[str, str]:
    """Match exact legal keys; unknown and unused encodings cannot select data."""
    choices = {f"{index:0{config.select_width}b}": word
               for index, word in enumerate(input_words(packed, config.data_width))}
    return (choices[select], "1") if select in choices else (config.default_bits, "0")


def interval_kind(config: MuxConfig, old_data: str, old_select: str, new_data: str, new_select: str) -> str:
    """Classify intervals whose outputs must remain unchanged during input activity."""
    if old_select != new_select:
        return "changing_selection"
    if old_data == new_data:
        return "stable"
    if set(new_select) & {"x", "z"} or int(new_select, 2) >= config.num_inputs:
        return "invalid"
    index = int(new_select, 2)
    old_word = input_words(old_data, config.data_width)[index]
    new_word = input_words(new_data, config.data_width)[index]
    return "unselected" if old_word == new_word else "selected"


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
    select: int | str
    words: tuple[int | str, ...]

    def packed_data(self, config: MuxConfig) -> str:
        assert len(self.words) == config.num_inputs, "Wrong number of source words"
        return "".join(bits(word, config.data_width) for word in reversed(self.words))


class MuxItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.inputs = inputs
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    packed_data: str
    select: str
    output: str
    valid: str
    requested: Inputs
    stage: str
    kind: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    signal: str
    value: str
    quiet: bool


class MuxDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            packed = item.inputs.packed_data(self.config)
            select = bits(item.inputs.select, self.config.select_width)
            kind = interval_kind(self.config, str(cocotb.top.i_data.value).lower(),
                                 str(cocotb.top.i_select.value).lower(), packed, select)
            self.active.update(item=item, stage="settled", kind=kind,
                               quiet=kind in ("stable", "unselected", "invalid"))
            cocotb.top.i_data.value = packed
            cocotb.top.i_select.value = select
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            # Once settled, all inputs remain stable until the next transaction.
            self.active["quiet"] = True
            await Timer(item.hold_ns, unit="ns")
            assert not self.active["sample"].is_set(), "Monitor missed the settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()


class MuxMonitor(uvm_monitor):
    """Read actual ports and capture both outputs throughout quiet intervals."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self, signal):
        handle = getattr(cocotb.top, signal)
        previous = str(handle.value).lower()
        while True:
            await handle.value_change
            quiet = self.active["quiet"]
            # Blocking defaults inside always_comb can expose intermediate
            # callback values in the same time step. Check functional activity
            # after delta cycles; a pulse lasting into this read-only phase fails.
            await ReadOnly()
            value = str(handle.value).lower()
            if value != previous:
                self.ap.write(OutputActivity(signal, value, quiet))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.output_activity(name)) for name in ("o_data", "o_select_valid")]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_data.value).lower(), str(cocotb.top.i_select.value).lower(),
                    str(cocotb.top.o_data.value).lower(), str(cocotb.top.o_select_valid.value).lower(),
                    item.inputs, self.active["stage"], self.active["kind"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()


class MuxScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.checks = self.held_checks = self.random_checks = self.simultaneous = 0
        self.activity = Counter()
        self.legal = set()
        self.invalid = set()
        self.unknown = set()
        self.legal_pairs = set()
        self.to_invalid = set()
        self.from_invalid = set()
        self.selected_activity = set()
        self.selected_bits = set()
        self.patterns = set()
        self.distinct = set()
        self.unselected_states = set()
        self.invalid_quiet = set()
        self.hold_classes = set()
        self.small_words = set()

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.quiet, (
                f"Unselected/stable input activity changed {observation.signal} to {observation.value}"
            )
            self.activity[observation.signal] += 1
            return
        config = self.config
        assert observation.packed_data == observation.requested.packed_data(config), "Data stimulus was coerced"
        assert observation.select == bits(observation.requested.select, config.select_width), "Selection was coerced"
        expected = expected_outputs(config, observation.packed_data, observation.select)
        assert (observation.output, observation.valid) == expected, (
            f"{observation.label}/{observation.stage}: select={observation.select}, "
            f"outputs={(observation.output, observation.valid)}, expected={expected}"
        )
        assert observation.valid in ("0", "1"), "Selection-valid must be known"
        if observation.stage == "held":
            self.held_checks += 1
            self.hold_classes.add("long" if observation.hold_ns >= 1 else "short")
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        words = input_words(observation.packed_data, config.data_width)
        selected = int(observation.select, 2) if set(observation.select) <= {"0", "1"} else None
        legal = selected is not None and selected < config.num_inputs
        if legal:
            self.legal.add(selected)
            self.selected_bits.update((selected, bit, value) for bit, value in enumerate(reversed(observation.output)))
            self.patterns.update((selected, name) for name in pattern_classes(words[selected]))
            if observation.label == "distinct_words" and len(set(words)) == config.num_inputs:
                self.distinct.add(selected)
            if config.data_width <= 8:
                self.small_words.add((selected, words[selected]))
        elif selected is not None:
            self.invalid.add(selected)
        else:
            self.unknown.add(observation.select)
        previous = self.previous
        if previous:
            old_selected = int(previous.select, 2) if set(previous.select) <= {"0", "1"} else None
            old_legal = old_selected is not None and old_selected < config.num_inputs
            kind = interval_kind(config, previous.packed_data, previous.select, observation.packed_data, observation.select)
            assert observation.kind == kind, "Quiet-interval classification did not match actual ports"
            if old_legal and legal:
                self.legal_pairs.add((old_selected, selected))
            if old_legal and selected is not None and not legal:
                self.to_invalid.add((old_selected, selected))
            if old_selected is not None and not old_legal and legal:
                self.from_invalid.add((old_selected, selected))
            if previous.select != observation.select and previous.packed_data != observation.packed_data:
                self.simultaneous += 1
            old_words = input_words(previous.packed_data, config.data_width)
            if kind == "selected":
                self.selected_activity.add(selected)
            elif kind == "unselected":
                for index, (before, after) in enumerate(zip(old_words, words, strict=True)):
                    if before != after and len(set(after)) == 1:
                        self.unselected_states.add((selected, index, after[0]))
            elif kind == "invalid":
                self.invalid_quiet.add(observation.select)
        self.previous = observation

    def report(self):
        config = self.config
        legal = set(range(config.num_inputs))
        invalid = set(config.invalid_encodings)
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z"}
        if config.data_width > 1:
            classes.update(("partial_unknown", "mixed_x_z"))
        unselected = {(selected, other, state) for selected, other, state in product(legal, legal, "01xz") if selected != other}
        goals = {
            "every_legal_selection": self.legal == legal,
            "every_invalid_binary_encoding": self.invalid == invalid,
            "every_four_state_unknown_selection": self.unknown == set(config.unknown_selects),
            "every_legal_transition_pair": self.legal_pairs == set(product(legal, repeat=2)),
            "every_legal_to_invalid_transition": self.to_invalid == set(product(legal, invalid)),
            "every_invalid_to_legal_transition": self.from_invalid == set(product(invalid, legal)),
            "every_selected_input_changes": self.selected_activity == legal,
            "every_selected_bit_preserves_four_states": self.selected_bits == set(product(legal, range(config.data_width), "01xz")),
            "every_input_pattern_class_selected": set(product(legal, classes)) <= self.patterns,
            "every_unselected_source_four_state_activity_suppressed": unselected <= self.unselected_states,
            "fixed_invalid_selection_suppresses_all_data_activity": ({f"{value:0{config.select_width}b}" for value in invalid} | set(config.unknown_selects)) <= self.invalid_quiet,
            "simultaneous_data_and_selection_changes": self.simultaneous > 0,
            "short_and_long_stable_intervals": self.hold_classes == {"short", "long"},
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        distinct_representable = config.num_inputs <= 1 << config.data_width
        if distinct_representable:
            goals["every_input_selected_with_distinct_source_words"] = self.distinct == legal
        if config.data_width <= 8:
            goals["exhaustive_binary_words_per_input"] = {(index, f"{value:0{config.data_width}b}") for index in legal for value in range(config.maximum + 1)} <= self.small_words
        if config.data_width <= 2:
            words = ("".join(word) for word in product("01xz", repeat=config.data_width))
            goals["exhaustive_four_state_words_per_input"] = set(product(legal, words)) <= self.small_words
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"NUM_INPUTS": config.num_inputs, "DATA_WIDTH": config.data_width,
                           "DEFAULT_VALUE": config.default_value, "SEL_WIDTH": config.select_width},
            "default_class": config.default_class, "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "goals": goals, "legal_selection_coverage_percent": 100 * len(self.legal) / config.num_inputs,
            "invalid_encoding_coverage_percent": 100 * len(self.invalid) / len(invalid) if invalid else None,
            "distinct_words_representable": distinct_representable,
            "bins": {"legal_selections": sorted(self.legal), "invalid_encodings": sorted(self.invalid),
                     "unknown_selections": sorted(self.unknown), "legal_transition_pairs": sorted(self.legal_pairs),
                     "legal_to_invalid": sorted(self.to_invalid), "invalid_to_legal": sorted(self.from_invalid),
                     "selected_input_activity": sorted(self.selected_activity), "selected_bit_values": sorted(self.selected_bits),
                     "selected_pattern_classes": sorted(self.patterns), "distinct_words_selected": sorted(self.distinct),
                     "unselected_source_states": sorted(self.unselected_states), "invalid_quiet_selections": sorted(self.invalid_quiet),
                     "hold_classes": sorted(self.hold_classes), "simultaneous_changes": self.simultaneous,
                     "output_activity": dict(self.activity), "unique_small_width_words": len(self.small_words)},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing mux coverage: {missing}"
        self.logger.info("Mux coverage PASS: %d transactions and %d held checks", self.checks, self.held_checks)


class MuxEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = MuxDriver("driver", self)
        self.monitor = MuxMonitor("monitor", self)
        self.scoreboard = MuxScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
