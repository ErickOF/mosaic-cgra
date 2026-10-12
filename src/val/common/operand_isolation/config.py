"""OperandIsolation config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
import os
from pathlib import Path
import cocotb


@dataclass(frozen=True)
class OperandIsolationConfig:
    width: int
    clamp_value: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> OperandIsolationConfig:
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/operand_isolation/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("OPERAND_ISOLATION_WIDTH", str(len(cocotb.top.o_data)))),
            clamp_value=int(os.getenv("OPERAND_ISOLATION_CLAMP_VALUE", "0"), 0),
            seed=int(os.getenv("OPERAND_ISOLATION_SEED", "20261011")),
            random_cycles=int(os.getenv("OPERAND_ISOLATION_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("OPERAND_ISOLATION_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and 0 <= config.clamp_value <= config.maximum
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def maximum(self) -> int:
        return (1 << self.width) - 1

    @property
    def clamp_bits(self) -> str:
        return f"{self.clamp_value:0{self.width}b}"

    @property
    def clamp_class(self) -> str:
        return "zero" if self.clamp_value == 0 else "one" if self.clamp_value == self.maximum else "mixed"

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    @property
    def patterns(self) -> tuple[str, ...]:
        values = {0, self.maximum, self.clamp_value, self.clamp_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.width))
        values.update(int((pattern * self.width)[:self.width], 2) for pattern in ("01", "10"))
        patterns = {f"{value:0{self.width}b}" for value in values}
        patterns.update(state * self.width for state in "xz")
        for bit, state, background in product(range(self.width), "xz", "01"):
            word = [background] * self.width
            word[self.width - bit - 1] = state
            patterns.add("".join(word))
        if self.width > 1:
            patterns.update((word * self.width)[:self.width] for word in ("xz", "zx"))
        return tuple(sorted(patterns))
