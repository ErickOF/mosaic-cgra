"""LaneMask config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import cocotb


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
