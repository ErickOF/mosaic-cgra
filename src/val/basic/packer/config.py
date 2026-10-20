"""Expected static geometry, supported modes and reproducible campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
from itertools import product
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class PackerConfig:
    elements: int
    source_width: int
    destination_width: int
    user_width: int
    signed: bool
    saturation: bool
    reverse: bool
    registered: bool
    asynchronous: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('PACKER_' + name, str(default)))
        flags = tuple(setting(name, default) for name, default in (
            ('SUPPORT_SIGNED', 1), ('SUPPORT_SATURATION', 1), ('SUPPORT_REVERSE', 1),
            ('REGISTER_OUTPUTS', 0), ('ASYNC_RESET', 0), ('CHECK_INTERNALS', 1)))
        assert all(value in (0, 1) for value in flags)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/packer/results.xml')).with_name('coverage.json')
        config = cls(setting('NUM_ELEMENTS', 4), setting('SRC_ELEMENT_WIDTH', 8),
                     setting('DST_ELEMENT_WIDTH', 16), setting('USER_WIDTH', 1), *map(bool, flags[:5]),
                     setting('SEED', 20261013), setting('RANDOM_CYCLES', 2000), bool(flags[5]),
                     os.getenv('PACKER_ASSERTION_PROBE', ''), Path(os.getenv('PACKER_COVERAGE_FILE', str(report))))
        assert min(config.elements, config.source_width, config.destination_width, config.user_width) >= 1
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for zero-delay RTL checking'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(NUM_ELEMENTS=self.elements, SRC_ELEMENT_WIDTH=self.source_width,
                    DST_ELEMENT_WIDTH=self.destination_width, USER_WIDTH=self.user_width,
                    SUPPORT_SIGNED=int(self.signed), SUPPORT_SATURATION=int(self.saturation),
                    SUPPORT_REVERSE=int(self.reverse), REGISTER_OUTPUTS=int(self.registered),
                    ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        from packer.transaction import INPUTS, OUTPUTS
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | dict(i_data=self.elements * self.source_width,
            o_data=self.elements * self.destination_width, i_user=self.user_width, o_user=self.user_width,
            **dict.fromkeys(('i_lane_valid', 'o_lane_valid', 'o_overflow', 'o_saturated'), self.elements))

    @property
    def narrowing(self):
        return self.source_width > self.destination_width

    @property
    def modes(self):
        return tuple(product(range(1 + self.signed), range(1 + (self.saturation and self.narrowing)), range(1 + self.reverse)))

    @property
    def result_width(self):
        return self.elements * (self.destination_width + 3) + 1 + self.user_width
