"""Decoder config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import cocotb


@dataclass(frozen=True)
class DecoderConfig:
    num_outputs: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> DecoderConfig:
        default_coverage = Path(os.getenv("COCOTB_RESULTS_FILE", "build/decoder/results.xml")).with_name("coverage.json")
        config = cls(
            num_outputs=int(os.getenv("DECODER_NUM_OUTPUTS", str(len(cocotb.top.o_decoded)))),
            seed=int(os.getenv("DECODER_SEED", "20261010")),
            random_cycles=int(os.getenv("DECODER_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("DECODER_COVERAGE_FILE", str(default_coverage))),
        )
        assert config.num_outputs >= 1
        assert config.random_cycles >= 1000, "Use at least 1000 randomized transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def select_width(self) -> int:
        return max(1, (self.num_outputs - 1).bit_length())

    @property
    def encodings(self) -> range:
        return range(1 << self.select_width)

    @property
    def invalid_encodings(self) -> range:
        return range(self.num_outputs, 1 << self.select_width)

    @property
    def sample_ns(self) -> float:
        # Advance one picosecond before ReadOnly for zero-delay RTL; callers
        # may request a larger settling interval for a separate timed flow.
        return max(0.001, self.settle_ns)
