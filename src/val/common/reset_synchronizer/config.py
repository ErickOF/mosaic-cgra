"""ResetSynchronizer config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from reset_synchronizer.model import picoseconds


@dataclass(frozen=True)
class ResetSynchronizerConfig:
    stages: int
    seed: int
    random_cycles: int
    period_ps: int
    near_ps: int
    pulse_ps: int
    check_stages: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> ResetSynchronizerConfig:
        structural = os.getenv("RESET_SYNCHRONIZER_CHECK_STAGES", "1")
        assert structural in ("0", "1")
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/reset_synchronizer/results.xml")).with_name("coverage.json")
        config = cls(
            stages=int(os.getenv("RESET_SYNCHRONIZER_STAGES", "2")),
            seed=int(os.getenv("RESET_SYNCHRONIZER_SEED", "20261011")),
            random_cycles=int(os.getenv("RESET_SYNCHRONIZER_RANDOM_CYCLES", "2000")),
            period_ps=picoseconds("TEST_CLOCK_PERIOD_NS", "4"),
            near_ps=picoseconds("RESET_SYNCHRONIZER_NEAR_NS", "0.01"),
            pulse_ps=picoseconds("RESET_SYNCHRONIZER_PULSE_NS", "0.01"),
            check_stages=structural == "1",
            coverage_file=Path(os.getenv("RESET_SYNCHRONIZER_COVERAGE_FILE", str(report))),
        )
        assert config.stages >= 2 and config.random_cycles >= 1000
        assert config.near_ps >= 3 and config.pulse_ps >= 3
        assert config.period_ps % 2 == 0 and config.period_ps // 2 > 2 * max(config.near_ps, config.pulse_ps)
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Use 1 ps precision or finer"
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "This suite verifies zero-delay RTL; use TEST_SETTLE_NS=0"
        return config
