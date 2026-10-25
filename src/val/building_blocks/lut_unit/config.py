"""Elaborated parameters and deterministic campaign settings."""
from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
from lut_unit.transaction import PORTS

from lut_unit.defaults import DEFAULTS


@dataclass(frozen=True)
class LutUnitConfig:
    parameters: dict
    seed: int
    random_cycles: int
    hdl_assertions: bool
    check_internals: bool
    coverage_file: Path

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('LUT_UNIT_' + name, str(default)), 0)
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/lut_unit/results.xml'))
        c = cls({n: setting(n, d) for n, d in DEFAULTS.items()}, setting('SEED', 20261022),
            setting('RANDOM_CYCLES', 2000), bool(setting('HDL_ASSERTIONS', 0)),
            bool(setting('CHECK_INTERNALS', 1)),
            Path(os.getenv('LUT_UNIT_COVERAGE_FILE', str(path.with_name('coverage.json')))))
        assert c.random_cycles >= 1000
        return c

    @cached_property
    def aliases(self):
        return dict(A=self.ADDRESS_WIDTH, W=self.OUTPUT_WIDTH, F=self.INDEX_FRACTION_WIDTH,
            B=self.NUM_BANKS, V=self.TABLE_VERSION_WIDTH, T=self.TABLE_ID_WIDTH,
            Q=self.QUALITY_ID_WIDTH, C=self.CONTEXT_ID_WIDTH, G=self.LOOKUP_TAG_WIDTH,
            INDEX_WIDTH=1+self.ADDRESS_WIDTH+self.INDEX_FRACTION_WIDTH,
            BANK_WIDTH=max(1, (self.NUM_BANKS-1).bit_length()),
            LOOKUP_QUEUE_OCCUPANCY_WIDTH=self.LOOKUP_RESPONSE_DEPTH.bit_length(),
            PROGRAM_QUEUE_OCCUPANCY_WIDTH=self.PROGRAM_RESPONSE_DEPTH.bit_length(),
            **{'lut_unit_pkg::ERROR_WIDTH': 4})

    @cached_property
    def widths(self):
        def width(w):
            if isinstance(w, int):
                return w
            result = 1
            for factor in w.split('*'):
                result *= self.aliases[factor]
            return result
        return {n: width(w) for n, (_, w) in PORTS.items()}
