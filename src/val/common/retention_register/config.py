"""Retention config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
import cocotb
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class RetentionConfig:
    width: int
    reset_value: int
    async_reset: bool
    has_enable: bool
    seed: int
    random_cycles: int
    period_ps: int
    check_image: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> RetentionConfig:
        flags = [os.getenv(name, default) for name, default in (
            ("RETENTION_REGISTER_ASYNC_RESET", "0"), ("RETENTION_REGISTER_HAS_ENABLE", "1"),
            ("RETENTION_REGISTER_CHECK_IMAGE", "1"),
        )]
        assert all(flag in ("0", "1") for flag in flags), "Static flags must be zero or one"
        period = Decimal(os.getenv("TEST_CLOCK_PERIOD_NS", "4")) * 1000
        assert period.is_finite() and period == int(period) and period >= 32 and int(period) % 4 == 0
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/retention_register/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("RETENTION_REGISTER_WIDTH", str(len(cocotb.top.o_q)))),
            reset_value=int(os.getenv("RETENTION_REGISTER_RESET_VALUE", "0"), 0),
            async_reset=flags[0] == "1", has_enable=flags[1] == "1", check_image=flags[2] == "1",
            seed=int(os.getenv("RETENTION_REGISTER_SEED", "20261011")),
            random_cycles=int(os.getenv("RETENTION_REGISTER_RANDOM_CYCLES", "2000")), period_ps=int(period),
            coverage_file=Path(os.getenv("RETENTION_REGISTER_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and 0 <= config.reset_value <= config.maximum
        assert config.random_cycles >= 1000 and get_time_from_sim_steps(1, unit="ps") <= 1
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use TEST_SETTLE_NS=0 for this zero-delay RTL suite"
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def reset_bits(self) -> str:
        return f"{self.reset_value:0{self.width}b}"

    @property
    def reset_class(self) -> str:
        return "zero" if self.reset_value == 0 else "one" if self.reset_value == self.maximum else "mixed"

    @property
    def patterns(self) -> tuple[str, ...]:
        values = {0, self.maximum, self.reset_value, self.reset_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.width))
        values.update(int((pattern * self.width)[:self.width], 2) for pattern in ("01", "10"))
        words = {f"{value:0{self.width}b}" for value in values}
        words.update(state * self.width for state in "xz")
        if self.width > 1:
            words.update((pattern * self.width)[:self.width] for pattern in ("xz", "zx", "0x", "1z"))
        return tuple(sorted(words))
