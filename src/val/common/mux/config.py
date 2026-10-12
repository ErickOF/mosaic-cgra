"""Mux config components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
import os
from pathlib import Path
import cocotb


@dataclass(frozen=True)
class MuxConfig:
    num_inputs: int
    data_width: int
    default_value: int
    seed: int
    random_cycles: int
    settle_ns: float
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> MuxConfig:
        width = len(cocotb.top.o_data)
        default_report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/mux/results.xml")).with_name("coverage.json")
        config = cls(
            num_inputs=int(os.getenv("MUX_NUM_INPUTS", str(len(cocotb.top.i_data) // width))),
            data_width=int(os.getenv("MUX_DATA_WIDTH", str(width))),
            default_value=int(os.getenv("MUX_DEFAULT_VALUE", "0"), 0),
            seed=int(os.getenv("MUX_SEED", "20261011")),
            random_cycles=int(os.getenv("MUX_RANDOM_CYCLES", "2000")),
            settle_ns=float(os.getenv("TEST_SETTLE_NS", "0")),
            coverage_file=Path(os.getenv("MUX_COVERAGE_FILE", str(default_report))),
        )
        assert config.num_inputs >= 1 and config.data_width >= 1
        assert 0 <= config.default_value <= config.maximum, "Default must fit the data port"
        assert config.random_cycles >= 1000, "Use at least 1000 random transactions"
        assert math.isfinite(config.settle_ns) and config.settle_ns >= 0
        return config

    @property
    def select_width(self) -> int:
        return max(1, (self.num_inputs - 1).bit_length())

    @property
    def maximum(self) -> int:
        return (1 << self.data_width) - 1

    @property
    def default_bits(self) -> str:
        return f"{self.default_value:0{self.data_width}b}"

    @property
    def default_class(self) -> str:
        return "zero" if self.default_value == 0 else "one" if self.default_value == self.maximum else "mixed"

    @property
    def invalid_encodings(self) -> range:
        return range(self.num_inputs, 1 << self.select_width)

    @property
    def unknown_selects(self) -> tuple[str, ...]:
        return tuple(word for values in product("01xz", repeat=self.select_width)
                     if set(word := "".join(values)) & {"x", "z"})

    @property
    def sample_ns(self) -> float:
        return max(0.001, self.settle_ns)

    @property
    def patterns(self) -> tuple[str, ...]:
        values = {0, self.maximum, self.default_value, self.default_value ^ self.maximum}
        values.update(1 << bit for bit in range(self.data_width))
        values.update(self.maximum ^ (1 << bit) for bit in range(self.data_width))
        values.update(int((pattern * self.data_width)[:self.data_width], 2) for pattern in ("01", "10"))
        patterns = {f"{value:0{self.data_width}b}" for value in values}
        patterns.update(state * self.data_width for state in "xz")
        for bit, state, background in product(range(self.data_width), "xz", "01"):
            word = [background] * self.data_width
            word[self.data_width - bit - 1] = state
            patterns.add("".join(word))
        if self.data_width > 1:
            patterns.update((word * self.data_width)[:self.data_width] for word in ("xz", "zx"))
        return tuple(sorted(patterns))
