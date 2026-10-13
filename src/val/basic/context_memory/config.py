"""Static context dimensions and reproducible campaign controls."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import product
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class ContextMemoryConfig:
    width: int
    depth: int
    slice_width: int
    read_ports: int
    raw: bool
    async_reset: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> ContextMemoryConfig:
        raw = int(os.getenv("CONTEXT_MEMORY_HAS_RAW_READBACK", "1"))
        asynchronous = int(os.getenv("CONTEXT_MEMORY_ASYNC_RESET", "0"))
        structural = int(os.getenv("CONTEXT_MEMORY_CHECK_INTERNALS", "1"))
        assert raw in (0, 1) and asynchronous in (0, 1) and structural in (0, 1)
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/context_memory/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("CONTEXT_MEMORY_CONTEXT_WIDTH", "256")),
            depth=int(os.getenv("CONTEXT_MEMORY_CONTEXT_DEPTH", "4")),
            slice_width=int(os.getenv("CONTEXT_MEMORY_WRITE_SLICE_WIDTH", "32")),
            read_ports=int(os.getenv("CONTEXT_MEMORY_NUM_READ_PORTS", "2")), raw=bool(raw), async_reset=bool(asynchronous),
            seed=int(os.getenv("CONTEXT_MEMORY_SEED", "20261012")),
            random_cycles=int(os.getenv("CONTEXT_MEMORY_RANDOM_CYCLES", "2000")), check_internals=bool(structural),
            probe=os.getenv("CONTEXT_MEMORY_ASSERTION_PROBE", ""),
            coverage_file=Path(os.getenv("CONTEXT_MEMORY_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and config.depth >= 1 and config.slice_width >= 1 and config.read_ports >= 1
        assert config.width % config.slice_width == 0 and config.random_cycles >= 1000
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use TEST_SETTLE_NS=0 for this zero-delay RTL suite"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Use 1 ps precision or finer"
        return config

    @property
    def address_width(self):
        return max(1, (self.depth - 1).bit_length())

    @property
    def slices(self):
        return self.width // self.slice_width

    @property
    def parameters(self):
        return dict(CONTEXT_WIDTH=self.width, CONTEXT_DEPTH=self.depth, WRITE_SLICE_WIDTH=self.slice_width,
                    NUM_READ_PORTS=self.read_ports, HAS_RAW_READBACK=int(self.raw), ASYNC_RESET=int(self.async_reset))

    @property
    def unknown_addresses(self):
        if self.address_width > 3:
            values = {state * self.address_width for state in "xz"}
            for base in (0, self.depth - 1):
                for index, state in product(range(self.address_width), "xz"):
                    word = list(f"{base:0{self.address_width}b}")
                    word[index] = state
                    values.add("".join(word))
            return tuple(sorted(values))
        return tuple(word for states in product("01xz", repeat=self.address_width)
                     if set(word := "".join(states)) & {"x", "z"})
