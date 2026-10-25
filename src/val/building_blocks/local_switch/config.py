"""Elaborated geometry and reproducible RTL-only campaign controls."""
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from local_switch.transaction import PORTS

DEFAULTS = dict(NUM_INPUTS=4, NUM_OUTPUTS=4, DATA_WIDTH=128, METADATA_WIDTH=32,
                CONTEXT_ID_WIDTH=8, CONNECTIVITY_MASK=65535, SUPPORT_MULTICAST=1, ASYNC_RESET=0)


@dataclass(frozen=True)
class LocalSwitchConfig:
    parameters: dict
    seed: int
    random_cycles: int
    check_internals: bool
    hdl_assertions: bool
    coverage_file: Path

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('LOCAL_SWITCH_' + name, str(default)), 0)
        flags = [setting('CHECK_INTERNALS', 1), setting('HDL_ASSERTIONS', 0)]
        assert set(flags) <= {0, 1}
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/local_switch/results.xml'))
        c = cls({n: setting(n, d) for n, d in DEFAULTS.items()}, setting('SEED', 20261021),
                setting('RANDOM_CYCLES', 2000), *map(bool, flags),
                Path(os.getenv('LOCAL_SWITCH_COVERAGE_FILE', str(path.with_name('coverage.json')))))
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL'
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return c

    @cached_property
    def aliases(self):
        i, o, d, m = self.NUM_INPUTS, self.NUM_OUTPUTS, self.DATA_WIDTH, self.METADATA_WIDTH
        return dict(I=i, O=o, D=d, M=m, C=self.CONTEXT_ID_WIDTH,
                    INPUT_SELECT_WIDTH=max(1, (i - 1).bit_length()), INPUT_DATA_WIDTH=i*d,
                    INPUT_METADATA_WIDTH=i*m, OUTPUT_DATA_WIDTH=o*d, OUTPUT_METADATA_WIDTH=o*m,
                    OUTPUT_SELECT_WIDTH=o*max(1, (i - 1).bit_length()), PENDING_WIDTH=i*o)

    @cached_property
    def edges(self):
        return {(i, o) for i in range(self.NUM_INPUTS) for o in range(self.NUM_OUTPUTS)
                if self.CONNECTIVITY_MASK >> (o * self.NUM_INPUTS + i) & 1}

    @cached_property
    def widths(self):
        return {n: self.aliases[w] if isinstance(w, str) else w for n, (_, w) in PORTS.items()}
