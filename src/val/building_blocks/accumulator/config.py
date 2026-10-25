"""Expected geometry and reproducible zero-delay assertion campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

LONG_STALL = 32
STREAM_LENGTH = 64


@dataclass(frozen=True)
class AccumulatorConfig:
    width: int
    lanes: int
    subtract: bool
    saturation: bool
    asynchronous: bool
    check_internals: bool
    hdl_assertions: bool
    seed: int
    random_cycles: int
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('ACCUMULATOR_' + name, str(default)), 0)
        features = tuple(setting(name, default) for name, default in (
            ('SUPPORT_SUBTRACT', 1), ('SUPPORT_SATURATION', 1), ('ASYNC_RESET', 0),
            ('CHECK_INTERNALS', 1), ('HDL_ASSERTIONS', 1)))
        assert all(value in (0, 1) for value in features)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/accumulator/results.xml')).with_name('coverage.json')
        config = cls(setting('ACC_WIDTH', 32), setting('NUM_LANES', 1), *map(bool, features),
            setting('SEED', 20261020), setting('RANDOM_CYCLES', 2000),
            os.getenv('ACCUMULATOR_ASSERTION_PROBE', ''), Path(os.getenv('ACCUMULATOR_COVERAGE_FILE', str(report))))
        assert config.width >= 1 and config.lanes >= 1 and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for RTL assertions'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(ACC_WIDTH=self.width, NUM_LANES=self.lanes, SUPPORT_SUBTRACT=int(self.subtract),
            SUPPORT_SATURATION=int(self.saturation), ASYNC_RESET=int(self.asynchronous), COMMAND_WIDTH=2)

    @property
    def widths(self):
        return dict(i_rstb=1, i_clock_enable=1, i_valid=1, i_command=2, i_lane_mask=self.lanes,
            i_data=self.width*self.lanes, i_signed=1, i_saturate=1, o_valid=1, o_illegal_operation=1,
            o_updated_mask=self.lanes, o_data=self.width*self.lanes, o_state_valid=self.lanes,
            o_state_signed=self.lanes, **{name:self.lanes for name in
                ('o_carry', 'o_borrow', 'o_overflow', 'o_saturated', 'o_zero', 'o_negative')})

    @property
    def all_lanes(self):
        return (1 << self.lanes)-1

    @property
    def word_mask(self):
        return (1 << self.width)-1
