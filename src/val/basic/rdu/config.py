"""Expected static allocation and reproducible campaign controls."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

STALL_LIMIT = 8


@dataclass(frozen=True)
class RduConfig:
    width: int
    channels: int
    total: int
    allocation: int
    asynchronous: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('RDU_' + name, str(default)), 0)
        asynchronous, structural = setting('ASYNC_RESET', 0), setting('CHECK_INTERNALS', 1)
        assert asynchronous in (0, 1) and structural in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/rdu/results.xml')).with_name('coverage.json')
        config = cls(setting('DATA_WIDTH', 32), setting('NUM_CHANNELS', 2), setting('TOTAL_DELAY_ENTRIES', 8),
            setting('CHANNEL_CAPACITY', 0x44), bool(asynchronous), setting('SEED', 20261019),
            setting('RANDOM_CYCLES', 2000), bool(structural), os.getenv('RDU_ASSERTION_PROBE', ''),
            Path(os.getenv('RDU_COVERAGE_FILE', str(report))))
        assert config.width >= 1 and config.channels >= 1 and config.total >= 0
        assert 0 <= config.allocation < 1 << (config.channels*config.delay_width)
        assert sum(config.capacities) == config.total and all(c <= config.total for c in config.capacities)
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for zero-delay RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def delay_width(self):
        return max(1, self.total.bit_length())

    @property
    def capacities(self):
        mask = (1 << self.delay_width) - 1
        return tuple((self.allocation >> (c*self.delay_width)) & mask for c in range(self.channels))

    @property
    def bases(self):
        return tuple(sum(self.capacities[:c]) for c in range(self.channels))

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, NUM_CHANNELS=self.channels, TOTAL_DELAY_ENTRIES=self.total,
            CHANNEL_CAPACITY=self.allocation, ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        return dict(i_rstb=1, i_advance=1, i_channel_enable=self.channels, i_delay=self.channels*self.delay_width,
            i_input_data=self.channels*self.width, i_input_valid=self.channels, i_flush=self.channels,
            o_output_data=self.channels*self.width, o_output_valid=self.channels,
            o_output_transfer=self.channels, o_channel_empty=self.channels, o_all_empty=1, o_config_error=self.channels)
