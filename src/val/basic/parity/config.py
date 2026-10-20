"""Expected static granule geometry and reproducible campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class ParityConfig:
    width: int
    granule_width: int
    seed: int
    random_cycles: int
    check_internals: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('PARITY_' + name, str(default)))
        structural = setting('CHECK_INTERNALS', 1)
        assert structural in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/parity/results.xml')).with_name('coverage.json')
        config = cls(setting('DATA_WIDTH', 32), setting('GRANULE_WIDTH', 8), setting('SEED', 20261013),
                     setting('RANDOM_CYCLES', 2000), bool(structural),
                     Path(os.getenv('PARITY_COVERAGE_FILE', str(report))))
        assert config.width >= 1 and config.granule_width >= 1 and config.width % config.granule_width == 0
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for zero-delay RTL checking'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parity_width(self):
        return self.width // self.granule_width

    @property
    def code_width(self):
        return self.width + self.parity_width

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, PARITY_GRANULE_WIDTH=self.granule_width)

    @property
    def widths(self):
        return dict(i_generate_data=self.width, i_check_data=self.width, i_check_parity=self.parity_width,
                    o_generated_parity=self.parity_width, o_checked_data=self.width,
                    o_error_vector=self.parity_width, o_granule_valid=self.parity_width, o_no_error=1, o_any_error=1)

    def granule(self, bit):
        return bit // self.granule_width if bit < self.width else bit - self.width

    def protected_bits(self, granule):
        return (*range(granule * self.granule_width, (granule + 1) * self.granule_width), self.width + granule)
