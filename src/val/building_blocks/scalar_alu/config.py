"""Reproducible ALU geometry, feature expectations and observation policy."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from scalar_alu.transaction import INPUTS, OUTPUTS

DEFAULTS = dict(DATA_WIDTH=32, SUPPORT_SATURATION=1, SUPPORT_MINMAX=1, OPCODE_WIDTH=5)


@dataclass(frozen=True)
class AluConfig:
    width: int
    saturation: int
    minmax: int
    opcode_width: int
    seed: int
    random_cycles: int
    check_internals: bool
    hdl_assertions: bool
    coverage_file: Path
    probe: str
    settle_ns: Decimal

    @classmethod
    def from_environment(cls):
        def read(name, default):
            return int(os.getenv('SCALAR_ALU_' + name, str(default)), 0)

        result = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/scalar_alu/results.xml'))
        c = cls(
            *(read(name, value) for name, value in DEFAULTS.items()),
            read('SEED', 20261022),
            read('RANDOM_CYCLES', 2000),
            bool(read('CHECK_INTERNALS', 1)),
            bool(read('HDL_ASSERTIONS', 1)),
            Path(os.getenv('SCALAR_ALU_COVERAGE_FILE', str(result.with_name('coverage.json')))),
            os.getenv('SCALAR_ALU_ASSERTION_PROBE', ''),
            Decimal(os.getenv('TEST_SETTLE_NS', '0')),
        )
        assert c.width >= 1 and c.opcode_width == 5
        assert c.saturation in (0, 1) and c.minmax in (0, 1)
        assert c.random_cycles >= 1000 and c.settle_ns >= 0
        return c

    @property
    def parameters(self):
        return dict(
            zip(
                DEFAULTS, (self.width, self.saturation, self.minmax, self.opcode_width), strict=True
            )
        )

    @property
    def mask(self):
        return (1 << self.width) - 1

    @property
    def widths(self):
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | dict(
            i_operand_a=self.width, i_operand_b=self.width, i_opcode=5, o_result=self.width
        )
