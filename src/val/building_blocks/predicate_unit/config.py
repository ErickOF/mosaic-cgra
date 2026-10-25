"""Elaboration parameters and reproducible simulation settings."""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from cocotb.utils import get_time_from_sim_steps

from predicate_unit.transaction import INPUTS, OUTPUTS

DEFAULTS = {"PRED_DEPTH": 4, "NUM_LANES": 4, "ASYNC_RESET": 0, "OPCODE_WIDTH": 4}


@dataclass(frozen=True)
class PredicateConfig:
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
            return int(os.getenv("PREDICATE_UNIT_" + name, str(default)), 0)

        result = Path(
            os.getenv("COCOTB_RESULTS_FILE", "build/predicate_unit/results.xml")
        )
        config = cls(
            {key: setting(key, value) for key, value in DEFAULTS.items()},
            setting("SEED", 20261022),
            setting("RANDOM_CYCLES", 2000),
            bool(setting("CHECK_INTERNALS", 1)),
            bool(setting("HDL_ASSERTIONS", 1)),
            Path(
                os.getenv(
                    "PREDICATE_UNIT_COVERAGE_FILE",
                    str(result.with_name("coverage.json")),
                )
            ),
            os.getenv("PREDICATE_UNIT_ASSERTION_PROBE", ""),
        )
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use zero-delay RTL"
        assert get_time_from_sim_steps(1, unit="ps") <= 1
        return config

    @property
    def depth(self):
        return self.parameters["PRED_DEPTH"]

    @property
    def lanes(self):
        return self.parameters["NUM_LANES"]

    @property
    def asynchronous(self):
        return self.parameters["ASYNC_RESET"]

    @property
    def address_width(self):
        return max(1, (self.depth - 1).bit_length())

    @property
    def mask(self):
        return (1 << self.lanes) - 1

    @property
    def widths(self):
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | {
            "i_opcode": 4,
            **dict.fromkeys(
                (
                    "i_lane_mask",
                    "i_predicate_input",
                    "o_result",
                    "o_result_valid",
                    "o_updated_mask",
                ),
                self.lanes,
            ),
            **dict.fromkeys(
                ("i_source_a_addr", "i_source_b_addr", "i_destination_addr"),
                self.address_width,
            ),
        }
