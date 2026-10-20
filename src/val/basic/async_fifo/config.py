"""Static FIFO parameters and reproducible digital-simulation settings."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path

from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class AsyncFifoConfig:
    width: int
    depth: int
    stages: int
    almost_full: int
    almost_empty: int
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> AsyncFifoConfig:
        depth = int(os.getenv("ASYNC_FIFO_DEPTH", "8"))
        structural = os.getenv("ASYNC_FIFO_CHECK_INTERNALS", "1")
        assert structural in ("0", "1")
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/async_fifo/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("ASYNC_FIFO_DATA_WIDTH", "32")), depth=depth,
            stages=int(os.getenv("ASYNC_FIFO_SYNC_STAGES", "2")),
            almost_full=int(os.getenv("ASYNC_FIFO_ALMOST_FULL_LEVEL", str(depth - 1))),
            almost_empty=int(os.getenv("ASYNC_FIFO_ALMOST_EMPTY_LEVEL", "1")),
            seed=int(os.getenv("ASYNC_FIFO_SEED", "20261012")),
            random_cycles=int(os.getenv("ASYNC_FIFO_RANDOM_CYCLES", "2000")),
            check_internals=structural == "1", probe=os.getenv("ASYNC_FIFO_ASSERTION_PROBE", ""),
            coverage_file=Path(os.getenv("ASYNC_FIFO_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and config.depth >= 2 and config.depth & (config.depth - 1) == 0
        assert config.stages >= 2 and 1 <= config.almost_full <= config.depth
        assert 0 <= config.almost_empty < config.depth and config.random_cycles >= 1000
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Use 1 ps precision or finer"
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "This suite verifies zero-delay RTL; use TEST_SETTLE_NS=0"
        return config

    @property
    def parameters(self) -> dict[str, int]:
        return dict(DATA_WIDTH=self.width, DEPTH=self.depth, SYNC_STAGES=self.stages,
                    ALMOST_FULL_LEVEL=self.almost_full, ALMOST_EMPTY_LEVEL=self.almost_empty)

    @property
    def pointer_width(self) -> int:
        return self.depth.bit_length()

    @property
    def latency_budget(self) -> int:
        """Fair-clock bound used only while both clocks and endpoint progress run."""
        return 8 * (self.depth + self.stages + 2)
