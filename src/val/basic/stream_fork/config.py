"""Expected fork geometry and reproducible campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

LONG_STALL = 32
STREAM_LENGTH = 64


@dataclass(frozen=True)
class StreamForkConfig:
    outputs: int
    width: int
    masked: bool
    asynchronous: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('STREAM_FORK_' + name, str(default)), 0)
        masked, asynchronous, internal = (setting(name, 0 if name != 'CHECK_INTERNALS' else 1)
            for name in ('HAS_DESTINATION_MASK', 'ASYNC_RESET', 'CHECK_INTERNALS'))
        assert all(value in (0, 1) for value in (masked, asynchronous, internal))
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/stream_fork/results.xml')).with_name('coverage.json')
        config = cls(setting('NUM_OUTPUTS', 2), setting('DATA_WIDTH', 32), bool(masked), bool(asynchronous),
            setting('SEED', 20261020), setting('RANDOM_CYCLES', 2000), bool(internal),
            os.getenv('STREAM_FORK_ASSERTION_PROBE', ''),
            Path(os.getenv('STREAM_FORK_COVERAGE_FILE', str(report))))
        assert config.outputs >= 1 and config.width >= 1 and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(NUM_OUTPUTS=self.outputs, DATA_WIDTH=self.width,
            HAS_DESTINATION_MASK=int(self.masked), ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        return dict(i_rstb=1, i_valid=1, o_ready=1, i_data=self.width,
            i_destination=self.outputs, o_valid=self.outputs, i_ready=self.outputs,
            o_data=self.width*self.outputs)

    @property
    def all_outputs(self):
        return (1 << self.outputs)-1
