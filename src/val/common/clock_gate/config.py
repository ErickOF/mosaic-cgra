"""ClockGate config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class ClockGateConfig:
    """Integer picoseconds avoid rounding stimulus onto a clock edge."""

    startup_enabled: bool
    seed: int
    random_cycles: int
    period_ps: int
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> ClockGateConfig:
        period = Decimal(os.getenv("TEST_CLOCK_PERIOD_NS", "4")) * 1000
        assert period.is_finite() and period == int(period)
        assert int(period) >= 16 and int(period) % 2 == 0, (
            "Use an even clock period of at least 16 ps"
        )
        startup = os.getenv("CLOCK_GATE_STARTUP_ENABLED", "0")
        assert startup in ("0", "1")
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/clock_gate/results.xml")).with_name("coverage.json")
        config = cls(
            startup_enabled=startup == "1",
            seed=int(os.getenv("CLOCK_GATE_SEED", "20261010")),
            random_cycles=int(os.getenv("CLOCK_GATE_RANDOM_CYCLES", "2000")),
            period_ps=int(period),
            coverage_file=Path(os.getenv("CLOCK_GATE_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.random_cycles >= 1000, "Use at least 1000 randomized cycles"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, (
            "The edge checks require simulator precision of 1 ps or finer"
        )
        return config

    @property
    def half_ps(self) -> int:
        return self.period_ps // 2
