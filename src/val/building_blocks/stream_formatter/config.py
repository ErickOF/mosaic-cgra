"""Public geometry, deterministic seed, and Python simulation settings."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from stream_formatter.transaction import PORTS

DEFAULTS = dict(DATA_WIDTH=128, NUM_LANES=4, COUNT_WIDTH=16, DATATYPE_WIDTH=6,
                CHANNEL_ID_WIDTH=4, CONTEXT_ID_WIDTH=8, REGISTER_OUTPUTS=1,
                ASYNC_RESET=0, MODE_WIDTH=1)


@dataclass(frozen=True)
class StreamFormatterConfig:
    parameters: dict
    seed: int
    random_cycles: int
    check_internals: bool
    coverage_file: Path
    probe: str

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('STREAM_FORMATTER_' + name, str(default)), 0)
        flag = setting('CHECK_INTERNALS', 1)
        assert flag in (0, 1)
        results = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/stream_formatter/results.xml'))
        c = cls({n: setting(n, d) for n, d in DEFAULTS.items()}, setting('SEED', 20261022),
                setting('RANDOM_CYCLES', 2000), bool(flag),
                Path(os.getenv('STREAM_FORMATTER_COVERAGE_FILE', str(results.with_name('coverage.json')))),
                os.getenv('STREAM_FORMATTER_ASSERTION_PROBE', ''))
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return c

    @property
    def aliases(self):
        return dict(D=self.DATA_WIDTH, L=self.NUM_LANES, C=self.COUNT_WIDTH,
                    F=self.DATATYPE_WIDTH, H=self.CHANNEL_ID_WIDTH, T=self.CONTEXT_ID_WIDTH,
                    B=self.DATA_WIDTH // 8)

    @property
    def widths(self):
        return {n: self.aliases[w] if isinstance(w, str) else w for n, (_, w) in PORTS.items()}
