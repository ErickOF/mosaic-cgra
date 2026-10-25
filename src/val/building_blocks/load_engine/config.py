"""Elaborated geometry and reproducible RTL-only campaign controls."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from load_engine.transaction import PORTS

DEFAULTS = dict(ADDR_WIDTH=32, DATA_WIDTH=128, COUNT_WIDTH=16, MAX_ELEMENT_BYTES=16,
                MAX_OUTSTANDING=8, SPACE_ID_WIDTH=2, CHANNEL_ID_WIDTH=4,
                CONTEXT_ID_WIDTH=8, ASYNC_RESET=0, MODE_WIDTH=2)


@dataclass(frozen=True)
class LoadEngineConfig:
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
            return int(os.getenv('LOAD_ENGINE_' + name, str(default)), 0)
        flags = [setting(name, 1) for name in ('CHECK_INTERNALS', 'HDL_ASSERTIONS')]
        assert set(flags) <= {0, 1}
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/load_engine/results.xml'))
        c = cls({n: setting(n, d) for n, d in DEFAULTS.items()}, setting('SEED', 20261021),
                setting('RANDOM_CYCLES', 2000), *map(bool, flags),
                Path(os.getenv('LOAD_ENGINE_COVERAGE_FILE', str(path.with_name('coverage.json')))))
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL'
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return c

    @property
    def max_log2(self):
        return self.MAX_ELEMENT_BYTES.bit_length() - 1

    @property
    def aliases(self):
        return dict(W=self.ADDR_WIDTH, D=self.DATA_WIDTH, C=self.COUNT_WIDTH,
                    S=self.SPACE_ID_WIDTH, H=self.CHANNEL_ID_WIDTH, T=self.CONTEXT_ID_WIDTH,
                    DATA_BYTES=self.DATA_WIDTH // 8,
                    TAG_WIDTH=max(1, (self.MAX_OUTSTANDING - 1).bit_length()),
                    OCCUPANCY_WIDTH=self.MAX_OUTSTANDING.bit_length(),
                    ELEMENT_SIZE_WIDTH=max(1, self.max_log2.bit_length()))

    @property
    def widths(self):
        return {n: self.aliases[w] if isinstance(w, str) else w for n, (_, w) in PORTS.items()}
