"""Expected combinational join geometry and reproducible traffic settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

LONG_WAIT = 32
STREAM_LENGTH = 64


@dataclass(frozen=True)
class StreamJoinConfig:
    inputs: int
    width: int
    masked: bool
    seed: int
    random_cycles: int
    check_parameters: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('STREAM_JOIN_' + name, str(default)), 0)
        masked, parameters = setting('HAS_REQUIRED_MASK', 0), setting('CHECK_PARAMETERS', 1)
        assert masked in (0, 1) and parameters in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/stream_join/results.xml')).with_name('coverage.json')
        config = cls(setting('NUM_INPUTS', 2), setting('DATA_WIDTH', 32), bool(masked),
            setting('SEED', 20261020), setting('RANDOM_CYCLES', 2000), bool(parameters),
            os.getenv('STREAM_JOIN_ASSERTION_PROBE', ''),
            Path(os.getenv('STREAM_JOIN_COVERAGE_FILE', str(report))))
        assert config.inputs >= 1 and config.width >= 1 and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(NUM_INPUTS=self.inputs, DATA_WIDTH=self.width, HAS_REQUIRED_MASK=int(self.masked))

    @property
    def widths(self):
        return dict(i_valid=self.inputs, o_ready=self.inputs, i_data=self.width*self.inputs,
            i_required=self.inputs, o_valid=1, i_ready=1, o_data=self.width*self.inputs, o_required=self.inputs)

    @property
    def all_inputs(self):
        return (1 << self.inputs)-1
