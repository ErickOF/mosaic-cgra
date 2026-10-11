"""Port-only PyUVM checking of independent, four-state lane-control decisions."""

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

SOURCES = ("i_lane_valid", "i_lane_mask", "i_lane_predicate")
OUTPUTS = ("o_lane_active", "o_lane_isolate", "o_lane_write_mask")


@dataclass(frozen=True)
class LaneMaskConfig:
    lanes: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> LaneMaskConfig:
        default_report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/lane_mask/results.xml")).with_name("coverage.json")
        config = cls(
            lanes=int(os.getenv("LANE_MASK_LANES", str(len(cocotb.top.o_lane_active)))),
            seed=int(os.getenv("LANE_MASK_SEED", "20261011")),
            random_cycles=int(os.getenv("LANE_MASK_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("LANE_MASK_COVERAGE_FILE", str(default_report))),
        )
        assert config.lanes >= 1, "LANES must be positive"
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.lanes) - 1

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    @property
    def patterns(self) -> tuple[int, ...]:
        """Finite masks for every lane, population count, tail, and alternating pattern."""
        values = {0, self.maximum}
        for bit in range(self.lanes):
            values.update((1 << bit, self.maximum ^ (1 << bit)))
        for count in range(self.lanes + 1):
            tail = (1 << count) - 1
            values.update((tail, tail << (self.lanes - count)))
        values.update(int((pattern * self.lanes)[:self.lanes], 2) for pattern in ("01", "10"))
        return tuple(sorted(values))


def bits(value: int | str, width: int) -> str:
    """Preserve X/Z and reject truncation before driving a port."""
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Input value does not fit the port"
        return f"{value:0{width}b}"
    result = value.lower()
    assert len(result) == width and set(result) <= set("01xz"), "Invalid four-state vector"
    return result


@dataclass(frozen=True)
class Inputs:
    operation_valid: int | str
    lane_valid: int | str
    lane_mask: int | str
    lane_predicate: int | str

    def ports(self, lanes: int) -> tuple[str, str, str, str]:
        return (bits(self.operation_valid, 1), bits(self.lane_valid, lanes),
                bits(self.lane_mask, lanes), bits(self.lane_predicate, lanes))


def expected_outputs(ports: tuple[str, str, str, str]) -> tuple[str, str, str]:
    """Evaluate one lane at a time using a truth table, without RTL internals.

    A zero dominates even unknown inputs; only four asserted controls activate
    a lane. Z is an unknown logic operand, so derived controls cannot be Z.
    """
    operation, valid, mask, predicate = ports
    active = []
    for controls in zip(valid, mask, predicate, strict=True):
        lane = (operation, *controls)
        active.append("0" if "0" in lane else "1" if all(bit == "1" for bit in lane) else "x")
    active_word = "".join(active)
    return active_word, active_word.translate(str.maketrans("01x", "10x")), active_word


def unknown_controls(ports: tuple[str, str, str, str]) -> tuple[str, ...]:
    """Local controls are required known only for a known, valid operation."""
    operation, *vectors = ports
    unknown = []
    if operation not in ("0", "1"):
        unknown.append("i_operation_valid")
    if operation == "1":
        unknown.extend(name for name, word in zip(SOURCES, vectors, strict=True) if set(word) & {"x", "z"})
    return tuple(unknown)


class LaneMaskItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, expected_unknown=()):
        super().__init__(label)
        self.inputs = inputs
        self.expected_unknown = expected_unknown


@dataclass(frozen=True)
class Observation:
    label: str
    ports: tuple[str, str, str, str]
    outputs: tuple[str, str, str]
    requested: Inputs
    expected_unknown: tuple[str, ...]


class LaneMaskDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            # Leave the preceding read-only phase before writing all controls.
            await Timer(1, unit="ps")
            self.active["item"] = item
            for name, value in zip(("i_operation_valid", *SOURCES), item.inputs.ports(self.config.lanes), strict=True):
                getattr(self.dut, name).value = value
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor did not consume the sample"
            self.seq_item_port.item_done()


class LaneMaskMonitor(uvm_monitor):
    """Read actual interface ports, including repeated unchanged transactions."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        while True:
            await self.active["sample"].wait()
            await ReadOnly()
            item = self.active["item"]
            self.ap.write(Observation(
                item.get_name(),
                tuple(str(getattr(cocotb.top, name).value).lower() for name in ("i_operation_valid", *SOURCES)),
                tuple(str(getattr(cocotb.top, name).value).lower() for name in OUTPUTS),
                item.inputs, item.expected_unknown,
            ))
            self.active["sample"].clear()


class LaneMaskScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.checks = self.random_checks = self.stable_checks = self.simultaneous_changes = 0
        self.control_violations = Counter()
        self.truth = set()
        self.individual_lanes = set()
        self.suppression = set()
        self.independence = set()
        self.populations = set()
        self.population_transitions = set()
        self.tails = set()
        self.predicates = set()
        self.valid_mask_cross = set()
        self.mask_predicate_cross = set()
        self.unknown_bins = set()
        self.invalid_unknowns = set()
        self.exhaustive = set()

    def write(self, observation):
        config = self.config
        ports, outputs = observation.ports, observation.outputs
        assert ports == observation.requested.ports(config.lanes), "A driven control was coerced"
        illegal = unknown_controls(ports)
        assert illegal == observation.expected_unknown, (
            f"{observation.label}: known-control assertions {illegal}, expected {observation.expected_unknown}"
        )
        for name in illegal:
            if not self.control_violations[name]:
                self.logger.info("Expected known-control assertion: %s contains X/Z", name)
            self.control_violations[name] += 1
        expected = expected_outputs(ports)
        for name, actual, reference in zip(OUTPUTS, outputs, expected, strict=True):
            assert actual == reference, f"{observation.label}: {ports}, {name}={actual}, expected {reference}"
        active, isolate, write = outputs
        assert isolate == active.translate(str.maketrans("01x", "10x")), "Isolation differs from canonical activity"
        assert write == active, "Write mask differs from canonical activity"
        assert all(set(word) <= set("01x") for word in outputs), "A derived control became high impedance"
        if ports[0] == "0":
            assert outputs == ("0" * config.lanes, "1" * config.lanes, "0" * config.lanes)
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        for lane, values in enumerate(zip(*(reversed(word) for word in ports[1:]), strict=True)):
            self.truth.add((lane, ports[0], *values))
            for index, (name, value) in enumerate(zip(SOURCES, values, strict=True)):
                if ports[0] == "1" and value == "0" and all(other == "1" for other_index, other in enumerate(values) if other_index != index):
                    self.suppression.add((lane, name))
                if value in ("x", "z"):
                    if ports[0] == "1":
                        self.unknown_bins.add((lane, name, value))
                    elif ports[0] == "0":
                        self.invalid_unknowns.add((lane, name, value))
            if ports[0] == "0" and values == ("1", "1", "1"):
                self.suppression.add((lane, "i_operation_valid"))
        if ports[0] in ("x", "z"):
            self.unknown_bins.add((-1, "i_operation_valid", ports[0]))
        known = all(set(word) <= {"0", "1"} for word in ports)
        if known:
            population = active.count("1")
            self.populations.add(population)
            if population == 1:
                self.individual_lanes.add(active[::-1].index("1"))
            valid, mask, predicate = (int(word, 2) for word in ports[1:])
            self.valid_mask_cross.add((valid, mask))
            self.mask_predicate_cross.add((mask, predicate))
            if ports[0] == "1" and valid == predicate == config.maximum:
                if mask in ((1 << count) - 1 for count in range(config.lanes + 1)):
                    self.tails.add(mask)
            if ports[0] == "1" and valid == mask == config.maximum:
                self.predicates.add(predicate)
        if (config.lanes <= 4 and known) or config.lanes <= 2:
            self.exhaustive.add(ports)
        previous = self.previous
        if previous:
            before_ports, before_outputs = previous.ports, previous.outputs
            if ports == before_ports:
                assert outputs == before_outputs, "Unchanged inputs retained history-dependent state"
                self.stable_checks += 1
            if all(before != after for before, after in zip(before_ports, ports, strict=True)):
                self.simultaneous_changes += 1
            if set(before_outputs[0] + active) <= {"0", "1"}:
                self.population_transitions.add((before_outputs[0].count("1"), active.count("1")))
            if ports[0] == before_ports[0] == "1":
                changed = [(source, bit, old, new) for source, (old_word, new_word) in enumerate(zip(before_ports[1:], ports[1:], strict=True))
                           for bit, (old, new) in enumerate(zip(reversed(old_word), reversed(new_word), strict=True)) if old != new]
                if len(changed) == 1 and changed[0][2:] in (("0", "1"), ("1", "0")):
                    source, bit, old, new = changed[0]
                    self.independence.add((bit, SOURCES[source], old, new))
                    offset = config.lanes - bit - 1
                    for old_word, new_word in zip(before_outputs, outputs, strict=True):
                        old_others = old_word[:offset] + old_word[offset + 1:]
                        new_others = new_word[:offset] + new_word[offset + 1:]
                        assert old_others == new_others, "Another lane's control changed an output"
        self.previous = observation

    def report(self):
        config = self.config
        lanes = range(config.lanes)
        required_unknowns = set(product(lanes, SOURCES, "xz")) | {(-1, "i_operation_valid", value) for value in "xz"}
        required_cross = set(product(config.patterns, repeat=2))
        goals = {
            "every_lane_binary_truth_table": set((lane, *values) for lane in lanes for values in product("01", repeat=4)) <= self.truth,
            "every_lane_four_state_truth_table": set((lane, *values) for lane in lanes for values in product("01xz", repeat=4)) <= self.truth,
            "every_lane_active_individually": self.individual_lanes == set(lanes),
            "every_source_disables_every_lane": set(product(lanes, ("i_operation_valid", *SOURCES))) <= self.suppression,
            "bidirectional_lane_independence": set((lane, source, old, new) for lane, source in product(lanes, SOURCES) for old, new in (("0", "1"), ("1", "0"))) <= self.independence,
            "all_active_population_counts": self.populations == set(range(config.lanes + 1)),
            "all_population_transition_pairs": set(product(range(config.lanes + 1), repeat=2)) <= self.population_transitions,
            "every_contiguous_tail": self.tails == {(1 << count) - 1 for count in range(config.lanes + 1)},
            "all_predicate_patterns": set(config.patterns) <= self.predicates,
            "lane_valid_by_architectural_mask": required_cross <= self.valid_mask_cross,
            "architectural_mask_by_predicate": required_cross <= self.mask_predicate_cross,
            "known_control_assertions": required_unknowns <= self.unknown_bins and set(self.control_violations) == {"i_operation_valid", *SOURCES},
            "invalid_operation_suppresses_unknown_lane_controls": set(product(lanes, SOURCES, "xz")) <= self.invalid_unknowns,
            "simultaneous_changes_to_all_controls": self.simultaneous_changes >= 2,
            "stable_repeated_transactions": self.stable_checks >= 64,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.lanes <= 4:
            words = tuple(f"{value:0{config.lanes}b}" for value in range(config.maximum + 1))
            goals["exhaustive_binary_vectors"] = set(product("01", words, words, words)) <= self.exhaustive
        if config.lanes <= 2:
            words = tuple("".join(word) for word in product("01xz", repeat=config.lanes))
            goals["exhaustive_four_state_vectors"] = set(product("01xz", words, words, words)) <= self.exhaustive
        return {
            "status": "PASS" if all(goals.values()) else "FAIL", "parameters": {"LANES": config.lanes},
            "seed": config.seed, "simulator": cocotb.SIM_NAME, "checked_transactions": self.checks,
            "random_transactions": self.random_checks, "stable_transactions": self.stable_checks,
            "expected_control_violations": dict(self.control_violations), "goals": goals,
            "bins": {"per_lane_truth_tables": sorted(self.truth), "individual_active_lanes": sorted(self.individual_lanes),
                     "source_suppression": sorted(self.suppression), "lane_independence": sorted(self.independence),
                     "populations": sorted(self.populations), "population_transitions": sorted(self.population_transitions),
                     "tail_masks": sorted(self.tails), "predicate_patterns": sorted(self.predicates),
                     "lane_valid_mask_cross": sorted(self.valid_mask_cross), "mask_predicate_cross": sorted(self.mask_predicate_cross),
                     "unknown_controls": sorted(self.unknown_bins), "invalid_operation_unknowns": sorted(self.invalid_unknowns),
                     "simultaneous_changes": self.simultaneous_changes, "vector_truth_table_entries": len(self.exhaustive)},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, passed in report["goals"].items() if not passed]
        assert not missing, f"Missing lane mask coverage: {missing}"
        self.logger.info("Lane mask coverage PASS: %d transactions", self.checks)


class LaneMaskEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = LaneMaskDriver("driver", self)
        self.monitor = LaneMaskMonitor("monitor", self)
        self.scoreboard = LaneMaskScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
