"""PriorityEncoder config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import cocotb


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
