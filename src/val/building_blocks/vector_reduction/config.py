"""Parameters, port geometry and reproducible simulation settings."""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from cocotb.utils import get_time_from_sim_steps

from vector_reduction.transaction import INPUTS, OUTPUTS

DEFAULTS = {
    "ELEMENT_WIDTH": 8,
    "NUM_ELEMENTS": 4,
    "ACC_WIDTH": 32,
    "SUPPORT_SUM": 1,
    "SUPPORT_MINMAX": 1,
    "SUPPORT_LOGICAL": 1,
    "LATENCY": 1,
    "MAX_LATENCY": 8,
    "ASYNC_RESET": 0,
    "OPCODE_WIDTH": 3,
    "RESULT_FORMAT_WIDTH": 2,
}


@dataclass(frozen=True)
class ReductionConfig:
    parameters: dict[str, int]
    seed: int
    random_cycles: int
    check_internals: bool
    hdl_assertions: bool
    coverage_file: Path
    probe: str

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv("VECTOR_REDUCTION_" + name, str(default)), 0)

        path = Path(os.getenv("COCOTB_RESULTS_FILE", "build/vector_reduction/results.xml"))
        c = cls(
            {k: setting(k, v) for k, v in DEFAULTS.items()},
            setting("SEED", 20261022),
            setting("RANDOM_CYCLES", 2000),
            bool(setting("CHECK_INTERNALS", 1)),
            bool(setting("HDL_ASSERTIONS", 1)),
            Path(os.getenv("VECTOR_REDUCTION_COVERAGE_FILE", str(path.with_name("coverage.json")))),
            os.getenv("VECTOR_REDUCTION_ASSERTION_PROBE", ""),
        )
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use zero-delay RTL"
        assert get_time_from_sim_steps(1, unit="ps") <= 1
        return c

    def __getattr__(self, name):
        keys = {
            "element": "ELEMENT_WIDTH",
            "count": "NUM_ELEMENTS",
            "accumulator": "ACC_WIDTH",
            "sum": "SUPPORT_SUM",
            "minmax": "SUPPORT_MINMAX",
            "logical": "SUPPORT_LOGICAL",
            "latency": "LATENCY",
            "asynchronous": "ASYNC_RESET",
        }
        if name not in keys:
            raise AttributeError(name)
        return self.parameters[keys[name]]

    @property
    def sum_width(self):
        return self.element + (self.count - 1).bit_length()

    @property
    def count_width(self):
        return self.count.bit_length()

    @property
    def widths(self):
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | {
            "i_opcode": 3,
            "i_element_mask": self.count,
            "i_data": self.count * self.element,
            "o_result": self.accumulator,
            "o_result_format": 2,
            "o_active_count": self.count_width,
        }

    @property
    def mask(self):
        return (1 << self.element) - 1

    @property
    def enabled_opcodes(self):
        return (
            ({0} if self.sum else set())
            | ({1, 2} if self.minmax else set())
            | ({3, 4} if self.logical else set())
        )
