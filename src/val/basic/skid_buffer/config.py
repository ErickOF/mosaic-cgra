"""Expected width/reset configuration and reproducible RTL campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

STALL_LIMIT = 8
LONG_STALL = 32
STREAM_LENGTH = 64


@dataclass(frozen=True)
class SkidBufferConfig:
    width: int
    asynchronous: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('SKID_BUFFER_' + name, str(default)), 0)
        asynchronous, internal = setting('ASYNC_RESET', 0), setting('CHECK_INTERNALS', 1)
        assert asynchronous in (0, 1) and internal in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/skid_buffer/results.xml')).with_name('coverage.json')
        config = cls(setting('DATA_WIDTH', 32), bool(asynchronous), setting('SEED', 20261019),
            setting('RANDOM_CYCLES', 2000), bool(internal), os.getenv('SKID_BUFFER_ASSERTION_PROBE', ''),
            Path(os.getenv('SKID_BUFFER_COVERAGE_FILE', str(report))))
        assert config.width >= 1 and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for zero-delay RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        return dict(i_rstb=1, i_valid=1, i_ready=1, o_valid=1, o_ready=1, i_data=self.width, o_data=self.width)
