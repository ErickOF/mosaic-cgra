"""Dff config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
import cocotb
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class DffConfig:
    width: int
    reset_value: int
    async_reset: bool
    has_enable: bool
    seed: int
    random_cycles: int
    period_ps: int
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> DffConfig:
        period = Decimal(os.getenv("TEST_CLOCK_PERIOD_NS", "4")) * 1000
        assert period.is_finite() and period == int(period)
        assert period >= 32 and int(period) % 4 == 0, "Use a clock period divisible by 4 ps and at least 32 ps"
        async_reset = os.getenv("DFF_ASYNC_RESET", "0")
        has_enable = os.getenv("DFF_HAS_ENABLE", "1")
        assert async_reset in ("0", "1") and has_enable in ("0", "1")
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/dff/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("DFF_WIDTH", str(len(cocotb.top.o_q)))),
            reset_value=int(os.getenv("DFF_RESET_VALUE", "0"), 0),
            async_reset=async_reset == "1", has_enable=has_enable == "1",
            seed=int(os.getenv("DFF_SEED", "20261010")),
            random_cycles=int(os.getenv("DFF_RANDOM_CYCLES", "2000")),
            period_ps=int(period),
            coverage_file=Path(os.getenv("DFF_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.width >= 1 and 0 <= config.reset_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 randomized cycles"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Waveform checking requires 1 ps precision or finer"
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "This suite checks zero-delay RTL; use TEST_SETTLE_NS=0"
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def reset_bits(self) -> str:
        return f"{self.reset_value:0{self.width}b}"

    @property
    def step_ps(self) -> int:
        return self.period_ps // 4
