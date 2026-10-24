"""Expected elaboration and reproducible controls for actual PyUVM runs."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from exp_unit.transaction import PORTS

DEFAULTS = {'INPUT_WIDTH': 16,
 'INPUT_FRACTION_WIDTH': 8,
 'RANGE_WIDTH': 40,
 'RANGE_FRACTION_WIDTH': 20,
 'LOG2E_FRACTION_WIDTH': 24,
 'INTERNAL_WIDTH': 24,
 'INTERNAL_FRACTION_WIDTH': 20,
 'OUTPUT_WIDTH': 16,
 'OUTPUT_FRACTION_WIDTH': 12,
 'TABLE_ADDRESS_WIDTH': 6,
 'SUPPORT_EXP_E': 1,
 'SUPPORT_EXP2': 1,
 'SUPPORT_INTERPOLATION': 1,
 'PIPELINE_DEPTH': 5,
 'OUTPUT_QUEUE_DEPTH': 2,
 'CONTEXT_ID_WIDTH': 8,
 'REQUEST_TAG_WIDTH': 8,
 'TABLE_PROTECTION': 0,
 'ASYNC_RESET': 0}


@dataclass(frozen=True)
class ExpUnitConfig:
    parameters: dict
    seed: int
    random_cycles: int
    check_internals: bool
    hdl_assertions: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('EXP_UNIT_' + name, str(default)), 0)
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/exp_unit/results.xml'))
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL'
        return cls({n: setting(n, v) for n, v in DEFAULTS.items()}, setting('SEED', 20261021),
                   setting('RANDOM_CYCLES', 2000), bool(setting('CHECK_INTERNALS', 1)),
                   bool(setting('HDL_ASSERTIONS', 0)),
                   Path(os.getenv('EXP_UNIT_COVERAGE_FILE', str(path.with_name('coverage.json')))))

    def __getattr__(self, name):
        if name in self.parameters:
            return self.parameters[name]
        raise AttributeError(name)

    @property
    def widths(self):
        p = self.parameters
        widths = dict(IW=p['INPUT_WIDTH'], OW=p['OUTPUT_WIDTH'], C=p['CONTEXT_ID_WIDTH'],
                      T=p['REQUEST_TAG_WIDTH'], EW=p['RANGE_WIDTH'] - p['RANGE_FRACTION_WIDTH'],
                      QW=p['OUTPUT_QUEUE_DEPTH'].bit_length())
        return {n: w if isinstance(w, int) else widths[w] for n, (_, w) in PORTS.items()}
