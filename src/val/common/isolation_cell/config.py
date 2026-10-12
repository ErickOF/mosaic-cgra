"""IsolationCell config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
import os
from pathlib import Path
import cocotb


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
