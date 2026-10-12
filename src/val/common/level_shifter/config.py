"""LevelShifter config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
import os
from pathlib import Path
import cocotb


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
