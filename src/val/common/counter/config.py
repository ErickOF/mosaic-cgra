"""Counter config components for specification-based PyUVM validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CounterConfig:
    """Expected elaboration parameters and reproducible campaign settings."""
    width: int
    reset_value: int
    saturate: bool
    async_reset: bool
    seed: int
    random_cycles: int
    clock_ns: float
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> CounterConfig:
        config = cls(
            width=int(os.getenv("COUNTER_WIDTH", "32")),
            reset_value=int(os.getenv("COUNTER_RESET_VALUE", "0"), 0),
            saturate=bool(int(os.getenv("COUNTER_SATURATE", "1"))),
            async_reset=bool(int(os.getenv("COUNTER_ASYNC_RESET", "0"))),
            seed=int(os.getenv("COUNTER_SEED", "20261010")),
            random_cycles=int(os.getenv("COUNTER_RANDOM_CYCLES", "2000")),
            clock_ns=float(os.getenv("TEST_CLOCK_PERIOD_NS", "4")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("COUNTER_COVERAGE_FILE", "counter_coverage.json")),
        )
        assert config.width >= 1
        assert 0 <= config.reset_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 randomized cycles"
        assert config.clock_ns > 0
        assert 0 <= config.settle_ns < config.clock_ns / 2
        assert config.sample_ns + 0.001 < config.clock_ns / 2
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def sample_ns(self) -> float:
        # Advance beyond the edge even for zero-delay RTL before ReadOnly.
        return max(self.settle_ns, 0.001)

    @property
    def representative_values(self) -> set[int]:
        return {
            0, 1, self.maximum, self.maximum - 1, self.reset_value,
            self.maximum // 2, 0xA55A & self.maximum,
        }
