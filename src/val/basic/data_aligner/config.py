"""Static interface dimensions and reproducible campaign controls."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class AlignerConfig:
    width: int
    user_width: int
    low: bool
    high: bool
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
            return int(os.getenv('DATA_ALIGNER_' + name, str(default)))
        flags = tuple(setting(name, default) for name, default in (
            ('SUPPORT_SHIFT_LOW', 1), ('SUPPORT_SHIFT_HIGH', 1), ('REGISTER_OUTPUTS', 0),
            ('ASYNC_RESET', 0), ('CHECK_INTERNALS', 1)))
        assert all(value in (0, 1) for value in flags)
        default_report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/data_aligner/results.xml')).with_name('coverage.json')
        config = cls(setting('DATA_WIDTH', 128), setting('USER_WIDTH', 1), *map(bool, flags[:4]),
                     setting('SEED', 20261013), setting('RANDOM_CYCLES', 2000), bool(flags[4]),
                     os.getenv('DATA_ALIGNER_ASSERTION_PROBE', ''),
                     Path(os.getenv('DATA_ALIGNER_COVERAGE_FILE', str(default_report))))
        assert config.width >= 8 and config.width % 8 == 0 and config.user_width >= 1
        assert config.low or config.high
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for this zero-delay RTL suite'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def word_bytes(self):
        return self.width // 8

    @property
    def offset_width(self):
        return max(1, (self.word_bytes - 1).bit_length())

    @property
    def directions(self):
        return tuple(direction for direction, enabled in enumerate((self.low, self.high)) if enabled)

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, USER_WIDTH=self.user_width, SUPPORT_SHIFT_LOW=int(self.low),
                    SUPPORT_SHIFT_HIGH=int(self.high), REGISTER_OUTPUTS=int(self.registered), ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        from data_aligner.transaction import INPUTS, OUTPUTS
        result = dict.fromkeys((*INPUTS, *OUTPUTS), 1)
        result.update({name: self.width for name in ('i_data_lo', 'i_data_hi', 'o_data_lo', 'o_data_hi', 'o_spill_data')})
        result.update({name: self.word_bytes for name in ('i_strb_lo', 'i_strb_hi', 'o_strb_lo', 'o_strb_hi', 'o_spill_strb')})
        result.update(i_offset=self.offset_width, i_user=self.user_width, o_user=self.user_width)
        return result

    @property
    def result_width(self):
        return 3 * self.width + 3 * self.word_bytes + 4 + self.user_width
