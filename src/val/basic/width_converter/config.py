"""Expected geometry, zero-delay sampling requirements and campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

STALL_LIMIT = 4
LONG_STALL = 32
STREAM_LENGTH = 64


@dataclass(frozen=True)
class WidthConverterConfig:
    input_width: int
    output_width: int
    unit_width: int
    user_width: int
    lsb_first: bool
    asynchronous: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('WIDTH_CONVERTER_' + name, str(default)), 0)
        lsb, asynchronous, internal = (setting(name, default) for name, default in
            (('LSB_FIRST', 1), ('ASYNC_RESET', 0), ('CHECK_INTERNALS', 1)))
        assert all(value in (0, 1) for value in (lsb, asynchronous, internal))
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/width_converter/results.xml')).with_name('coverage.json')
        config = cls(setting('IN_WIDTH', 32), setting('OUT_WIDTH', 128), setting('UNIT_WIDTH', 8),
            setting('USER_WIDTH', 1), bool(lsb), bool(asynchronous), setting('SEED', 20261020),
            setting('RANDOM_CYCLES', 2000), bool(internal), os.getenv('WIDTH_CONVERTER_ASSERTION_PROBE', ''),
            Path(os.getenv('WIDTH_CONVERTER_COVERAGE_FILE', str(report))))
        assert min(config.input_width, config.output_width, config.unit_width, config.user_width) >= 1
        assert config.input_width % config.unit_width == config.output_width % config.unit_width == 0
        assert max(config.input_width, config.output_width) % min(config.input_width, config.output_width) == 0
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(IN_WIDTH=self.input_width, OUT_WIDTH=self.output_width, UNIT_WIDTH=self.unit_width,
            USER_WIDTH=self.user_width, LSB_FIRST=int(self.lsb_first), ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        return dict(i_rstb=1, i_flush=1, i_valid=1, o_ready=1, i_data=self.input_width,
            i_keep=self.in_units, i_last=1, i_user=self.user_width, o_valid=1, i_ready=1,
            o_data=self.output_width, o_keep=self.out_units, o_last=1, o_user=self.user_width, o_busy=1)

    @property
    def in_units(self):
        return self.input_width // self.unit_width

    @property
    def out_units(self):
        return self.output_width // self.unit_width

    @property
    def wide_units(self):
        return max(self.in_units, self.out_units)

    @property
    def ratio(self):
        return max(self.input_width, self.output_width) // min(self.input_width, self.output_width)

    @property
    def mode(self):
        return 'pack' if self.input_width < self.output_width else 'unpack' if self.input_width > self.output_width else 'equal'
