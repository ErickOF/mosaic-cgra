"""Parameters, port geometry and reproducible simulation settings."""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from cocotb.utils import get_time_from_sim_steps

from vector_lane.transaction import INPUTS, OUTPUTS

DEFAULTS = {
    "ELEMENT_WIDTH": 8,
    "ACC_WIDTH": 32,
    "SUPPORT_MUL": 1,
    "SUPPORT_MAC": 1,
    "SUPPORT_SATURATION": 1,
    "SUPPORT_MINMAX": 1,
    "LANE_LATENCY": 1,
    "MUL_LATENCY": 1,
    "MAC_LATENCY": 1,
    "MAX_LANE_LATENCY": 4,
    "ASYNC_RESET": 0,
    "OPCODE_WIDTH": 5,
    "RESULT_FORMAT_WIDTH": 2,
}


@dataclass(frozen=True)
class LaneConfig:
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
            return int(os.getenv("VECTOR_LANE_" + name, str(default)), 0)

        path = Path(os.getenv("COCOTB_RESULTS_FILE", "build/vector_lane/results.xml"))
        c = cls(
            {k: setting(k, v) for k, v in DEFAULTS.items()},
            setting("SEED", 20261022),
            setting("RANDOM_CYCLES", 2000),
            bool(setting("CHECK_INTERNALS", 1)),
            bool(setting("HDL_ASSERTIONS", 1)),
            Path(os.getenv("VECTOR_LANE_COVERAGE_FILE", str(path.with_name("coverage.json")))),
            os.getenv("VECTOR_LANE_ASSERTION_PROBE", ""),
        )
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use zero-delay RTL"
        assert get_time_from_sim_steps(1, unit="ps") <= 1
        return c

    def __getattr__(self, name):
        keys = {
            "element": "ELEMENT_WIDTH",
            "accumulator": "ACC_WIDTH",
            "mul": "SUPPORT_MUL",
            "mac": "SUPPORT_MAC",
            "saturation": "SUPPORT_SATURATION",
            "minmax": "SUPPORT_MINMAX",
            "latency": "LANE_LATENCY",
            "mul_latency": "MUL_LATENCY",
            "mac_latency": "MAC_LATENCY",
            "asynchronous": "ASYNC_RESET",
        }
        if name not in keys:
            raise AttributeError(name)
        return self.parameters[keys[name]]

    @property
    def widths(self):
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | {
            "i_opcode": 5,
            "i_operand_a": self.element,
            "i_operand_b": self.element,
            "i_accumulator": self.accumulator,
            "o_result": self.accumulator,
            "o_result_format": 2,
        }

    @property
    def mask(self):
        return (1 << self.element) - 1

    @property
    def alu(self):
        # Reuse the independent released ALU oracle; lane extension/status is checked here.
        return SimpleNamespace(
            width=self.element,
            mask=self.mask,
            saturation=self.saturation,
            minmax=self.minmax,
            widths=self.widths | {"o_result": self.element},
        )
