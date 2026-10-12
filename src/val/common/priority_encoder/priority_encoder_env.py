"""Independent port-based, four-state PyUVM checks for fixed-priority selection."""

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

SIGNALS = ("o_valid", "o_index", "o_onehot", "o_multiple")


@dataclass(frozen=True)
class PriorityEncoderConfig:
    width: int
    lsb_high_priority: bool
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> PriorityEncoderConfig:
        direction = os.getenv("PRIORITY_ENCODER_LSB_HIGH_PRIORITY", "1")
        assert direction in ("0", "1"), "Priority direction must be a static boolean"
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/priority_encoder/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("PRIORITY_ENCODER_WIDTH", str(len(cocotb.top.i_request)))),
            lsb_high_priority=direction == "1", seed=int(os.getenv("PRIORITY_ENCODER_SEED", "20261011")),
            random_cycles=int(os.getenv("PRIORITY_ENCODER_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("PRIORITY_ENCODER_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and config.random_cycles >= 1000
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def index_width(self) -> int:
        return max(1, (self.width - 1).bit_length())

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    def higher(self, left: int, right: int) -> bool:
        return left < right if self.lsb_high_priority else left > right

    @property
    def population_cross(self) -> set[tuple[int, int]]:
        """Only populations achievable without asserting a higher-priority bit."""
        return {(index, count) for index in range(self.width)
                for count in range(1, (self.width - index if self.lsb_high_priority else index + 1) + 1)}


def bits(value: int | str, width: int) -> str:
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Request stimulus does not fit the port"
        return f"{value:0{width}b}"
    value = value.lower()
    assert len(value) == width and set(value) <= set("01xz"), "Invalid four-state stimulus"
    return value


@dataclass(frozen=True)
class Reference:
    outputs: tuple[str, str, str, str]
    ambiguous: bool
    selected: int | None
    known: frozenset[int]
    unknown: frozenset[int]


def expected_outputs(config: PriorityEncoderConfig, request: str) -> Reference:
    """Use sets of possible winners/count bounds, rather than the RTL scan.

Unknown bits can be either zero or one. An optional no-request outcome counts
as a separate outcome, so even one isolated unknown request is ambiguous.
No enumeration of 2**WIDTH completions is needed for wide unknown vectors.
"""
    known = frozenset(index for index, state in enumerate(reversed(request)) if state == "1")
    unknown = frozenset(index for index, state in enumerate(reversed(request)) if state in "xz")
    best_known = (min(known) if config.lsb_high_priority else max(known)) if known else None
    possible = {best_known} | {index for index in unknown if best_known is None or config.higher(index, best_known)}
    ambiguous = len(possible) > 1
    valid = "1" if known else "x" if unknown else "0"
    multiple = "1" if len(known) > 1 else "0" if len(known) + len(unknown) <= 1 else "x"
    selected = best_known if not ambiguous else None
    index = "x" * config.index_width if ambiguous else f"{selected or 0:0{config.index_width}b}"
    onehot = "x" * config.width if ambiguous else f"{0 if selected is None else 1 << selected:0{config.width}b}"
    return Reference((valid, index, onehot, multiple), ambiguous, selected, known, unknown)


def pattern_classes(value: int, width: int) -> set[str]:
    population = value.bit_count()
    classes = set()
    if population == 0:
        classes.add("none")
    if population == 1:
        classes.add("single")
    if population == 2:
        classes.add("pair")
    if value == (1 << width) - 1:
        classes.add("all")
    if population:
        low, high = (value & -value).bit_length() - 1, value.bit_length() - 1
        classes.add("contiguous" if population == high - low + 1 else "noncontiguous")
    if value in (int((pattern * width)[:width], 2) for pattern in ("01", "10")):
        classes.add("alternating")
    return classes


class PriorityEncoderItem(uvm_sequence_item):
    def __init__(self, label, request, *, expected_ambiguity=False, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.request, self.expected_ambiguity, self.hold_ns = request, expected_ambiguity, hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    request: str
    outputs: tuple[str, str, str, str]
    requested: int | str
    expected_ambiguity: bool
    stage: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    signal: str
    value: str
    quiet: bool


class PriorityEncoderDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            request = bits(item.request, self.config.width)
            self.active.update(item=item, stage="settled", quiet=str(cocotb.top.i_request.value).lower() == request)
            cocotb.top.i_request.value = request
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


class PriorityEncoderMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self, signal):
        handle = getattr(cocotb.top, signal)
        previous = str(handle.value).lower()
        while True:
            await handle.value_change
            quiet = self.active["quiet"]
            # Ignore transient callback values inside one combinational delta
            # evaluation, but catch finite pulses before transaction sampling.
            await ReadOnly()
            value = str(handle.value).lower()
            if value != previous:
                self.ap.write(OutputActivity(signal, value, quiet))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.output_activity(signal)) for signal in SIGNALS]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_request.value).lower(),
                    tuple(str(getattr(cocotb.top, signal).value).lower() for signal in SIGNALS),
                    item.request, item.expected_ambiguity, self.active["stage"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()


class PriorityEncoderScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.checks = self.held_checks = self.random_checks = self.ambiguity_violations = 0
        self.activity = Counter()
        self.populations, self.selected, self.pairs, self.population_cross = set(), set(), set(), set()
        self.extremes, self.pattern_cross, self.bits_seen, self.bit_transitions = set(), set(), set(), set()
        self.unknown_cases, self.masked_activity, self.winner_pairs, self.holds = set(), set(), set(), set()
        self.binary_vectors, self.four_state_vectors = set(), set()
        self.unknown_modes = Counter()

    def assert_known_consistency(self, observation, reference):
        """Check interface invariants separately from the reference tuple."""
        request = int(observation.request, 2)
        valid, index, onehot, multiple = (int(value, 2) for value in observation.outputs)
        assert valid == bool(request), "Valid does not match request reduction"
        assert onehot.bit_count() <= 1, "Onehot0 assertion failed"
        assert onehot & ~request == 0, "Granted request does not exist"
        assert multiple == (request.bit_count() > 1), "Multiple indication is incorrect"
        if valid:
            assert onehot.bit_count() == 1 and 0 <= index < self.config.width
            assert onehot == 1 << index and request & onehot
            assert all(not self.config.higher(other, index) for other in reference.known), "Higher-priority request was bypassed"
        else:
            assert index == onehot == multiple == 0, "No-request outputs retained stale state"

    def write(self, observation):
        if isinstance(observation, OutputActivity):
            assert not observation.quiet, f"Stable request changed {observation.signal} to {observation.value}"
            self.activity[observation.signal] += 1
            return
        config = self.config
        assert observation.request == bits(observation.requested, config.width), "Request stimulus was coerced"
        reference = expected_outputs(config, observation.request)
        # Deliberate ambiguous requests acknowledge a live assertion failure;
        # untagged ambiguity is fatal and is proven by separate X/Z probes.
        try:
            assert not reference.ambiguous, f"Ambiguous-request assertion failed: i_request={observation.request}"
        except AssertionError:
            if not observation.expected_ambiguity:
                raise
            if observation.stage == "settled":
                if not self.ambiguity_violations:
                    self.logger.info("Expected ambiguous-request assertion: i_request=%s", observation.request)
                self.ambiguity_violations += 1
        else:
            assert not observation.expected_ambiguity, "Expected ambiguous request was not ambiguous"
        assert observation.outputs == reference.outputs, (
            f"{observation.label}/{observation.stage}: request={observation.request}, "
            f"outputs={observation.outputs}, expected={reference.outputs}"
        )
        if not reference.unknown:
            self.assert_known_consistency(observation, reference)
        if observation.stage == "held":
            self.held_checks += 1
            if not reference.unknown:
                count = len(reference.known)
                self.holds.add(("none" if count == 0 else "single" if count == 1 else "multiple", "long" if observation.hold_ns >= 1 else "short"))
            return
        assert observation.stage == "settled"
        self.checks += 1
        self.random_checks += observation.label.startswith("random_")
        self.bits_seen.update(enumerate(reversed(observation.request)))
        if config.width <= 5:
            self.four_state_vectors.add(observation.request)
        if not reference.unknown:
            population = len(reference.known)
            self.populations.add(population)
            if config.width <= 8:
                self.binary_vectors.add(observation.request)
            if population:
                self.selected.add(reference.selected)
                self.population_cross.add((reference.selected, population))
                self.extremes.add((min(reference.known), max(reference.known)))
            if population == 2:
                self.pairs.add(tuple(sorted(reference.known)))
            classes = pattern_classes(int(observation.request, 2), config.width)
            if observation.label.startswith("random_"):
                classes.add("random")
            self.pattern_cross.update((name, observation.outputs[3]) for name in classes)
        else:
            self.unknown_modes["ambiguous" if reference.ambiguous else "masked"] += 1
            best_known = (min(reference.known) if config.lsb_high_priority else max(reference.known)) if reference.known else None
            for index in reference.unknown:
                relation = "no_known" if best_known is None else "higher" if config.higher(index, best_known) else "lower"
                self.unknown_cases.add((index, observation.request[config.width - index - 1], relation))
        if self.previous:
            previous, old_reference = self.previous
            self.bit_transitions.update((index, before, after) for index, (before, after) in enumerate(zip(reversed(previous.request), reversed(observation.request), strict=True)))
            if old_reference.selected is not None and reference.selected is not None:
                self.winner_pairs.add((old_reference.selected, reference.selected))
                if old_reference.selected == reference.selected:
                    for index, (before, after) in enumerate(zip(reversed(previous.request), reversed(observation.request), strict=True)):
                        if before != after and config.higher(reference.selected, index):
                            self.masked_activity.add((reference.selected, index, after))
        self.previous = observation, reference

    def report(self):
        config = self.config
        classes = {("none", "0"), ("single", "0"), ("all", "1" if config.width > 1 else "0"),
                   ("contiguous", "0"), ("random", "0")}
        if config.width > 1:
            classes.update((("pair", "1"), ("contiguous", "1"), ("random", "1")))
        if config.width > 2:
            classes.add(("noncontiguous", "1"))
        for pattern in ("01", "10"):
            classes.add(("alternating", "1" if int((pattern * config.width)[:config.width], 2).bit_count() > 1 else "0"))
        unknown_bins = {(index, state, "no_known") for index, state in product(range(config.width), "xz")}
        for index, other, state in product(range(config.width), range(config.width), "xz"):
            if index != other:
                unknown_bins.add((index, state, "higher" if config.higher(index, other) else "lower"))
        masked = {(winner, other, state) for winner, other, state in product(range(config.width), range(config.width), "01xz") if config.higher(winner, other)}
        contention = {index for index, count in config.population_cross if count > 1}
        hold_states = {"none", "single", "multiple"} if config.width > 1 else {"none", "single"}
        goals = {
            "every_request_selected": self.selected == set(range(config.width)),
            "every_population_count": self.populations == set(range(config.width + 1)),
            "every_simultaneous_request_pair": self.pairs == {(low, high) for low in range(config.width) for high in range(low + 1, config.width)},
            "reachable_selected_index_population_cross": self.population_cross == config.population_cross,
            "every_eligible_index_selected_under_contention": {index for index, count in self.population_cross if count > 1} == contention,
            "lowest_highest_asserted_index_cross": self.extremes == {(low, high) for low in range(config.width) for high in range(low, config.width)},
            "pattern_class_multiple_cross": classes <= self.pattern_cross,
            "every_request_bit_four_states": self.bits_seen == set(product(range(config.width), "01xz")),
            "every_request_bit_ordered_four_state_transition": self.bit_transitions == set(product(range(config.width), "01xz", "01xz")),
            "unknown_higher_lower_and_no_known_cases": unknown_bins <= self.unknown_cases,
            "lower_priority_activity_preserves_winner": masked <= self.masked_activity,
            "every_ordered_winner_transition": self.winner_pairs == set(product(range(config.width), repeat=2)),
            "active_ambiguous_request_assertions": self.ambiguity_violations > 0,
            "short_and_long_holds_by_population_class": set(product(hold_states, ("short", "long"))) <= self.holds,
            "every_transaction_checked_after_hold": self.held_checks == self.checks,
            "random_activity": self.random_checks == config.random_cycles,
        }
        if config.width <= 8:
            goals["exhaustive_binary_request_vectors"] = self.binary_vectors == {f"{value:0{config.width}b}" for value in range(config.maximum + 1)}
        if config.width <= 5:
            goals["exhaustive_four_state_request_vectors"] = self.four_state_vectors == {"".join(word) for word in product("01xz", repeat=config.width)}
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {"WIDTH": config.width, "LSB_HIGH_PRIORITY": int(config.lsb_high_priority), "INDEX_WIDTH": config.index_width},
            "seed": config.seed, "simulator": cocotb.SIM_NAME,
            "checked_transactions": self.checks, "held_checks": self.held_checks, "random_transactions": self.random_checks,
            "expected_ambiguity_violations": self.ambiguity_violations, "output_transitions": dict(self.activity),
            "goals": goals, "selected_index_coverage_percent": 100 * len(self.selected) / config.width,
            "contention_ineligible_indices": sorted(set(range(config.width)) - contention),
            "bins": {"selected_indices": sorted(self.selected), "populations": sorted(self.populations),
                     "request_pairs": sorted(self.pairs), "selected_index_population": sorted(self.population_cross),
                     "lowest_highest_indices": sorted(self.extremes), "pattern_multiple": sorted(self.pattern_cross),
                     "request_bit_values": sorted(self.bits_seen), "request_bit_transitions": sorted(self.bit_transitions),
                     "unknown_cases": sorted(self.unknown_cases), "unknown_modes": dict(self.unknown_modes),
                     "masked_request_activity": sorted(self.masked_activity), "winner_transitions": sorted(self.winner_pairs),
                     "holds": sorted(self.holds), "binary_vectors": len(self.binary_vectors) if config.width <= 8 else None,
                     "four_state_vectors": len(self.four_state_vectors) if config.width <= 5 else None},
        }

    def check_phase(self):
        report = self.report()
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        missing = [name for name, covered in report["goals"].items() if not covered]
        assert not missing, f"Missing priority encoder coverage: {missing}"
        self.logger.info("Priority encoder coverage PASS: %d transactions", self.checks)


class PriorityEncoderEnv(uvm_env):
    def build_phase(self):
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = PriorityEncoderDriver("driver", self)
        self.monitor = PriorityEncoderMonitor("monitor", self)
        self.scoreboard = PriorityEncoderScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
