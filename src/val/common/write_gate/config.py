"""WriteGate config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import cocotb


@dataclass(frozen=True)
class WriteGateConfig:
    width: int
    integration: bool
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> WriteGateConfig:
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/write_gate/results.xml")).with_name("coverage.json")
        mode = os.getenv("WRITE_GATE_INTEGRATION", "0")
        assert mode in ("0", "1"), "WRITE_GATE_INTEGRATION must be 0 or 1"
        config = cls(
            int(os.getenv("WRITE_GATE_WIDTH", str(len(cocotb.top.o_write_enable)))),
            mode == "1", int(os.getenv("WRITE_GATE_SEED", "20261011")),
            int(os.getenv("WRITE_GATE_RANDOM_CYCLES", "2000")),
            float(os.getenv("TEST_SETTLE_NS", "0")),
            Path(os.getenv("WRITE_GATE_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        assert config.integration == hasattr(cocotb.top, "i_clk"), "Wrong fixture for integration mode"
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)
