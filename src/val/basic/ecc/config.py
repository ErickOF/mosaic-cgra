"""Protected-word geometry and reproducible ECC campaigns."""

from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class EccConfig:
    width: int
    seed: int
    random_cycles: int
    check_internals: bool
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/ecc/results.xml')).with_name('coverage.json')
        structural = int(os.getenv('ECC_CHECK_INTERNALS', '1'))
        assert structural in (0, 1)
        config = cls(int(os.getenv('ECC_DATA_WIDTH', '32')), int(os.getenv('ECC_SEED', '20261013')),
                     int(os.getenv('ECC_RANDOM_CYCLES', '2000')), bool(structural),
                     Path(os.getenv('ECC_COVERAGE_FILE', str(report))))
        assert 1 <= config.width <= 256 and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for this combinational RTL suite'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @cached_property
    def parity_bits(self):
        count = 1
        while 2 ** count < self.width + count + 1:
            count += 1
        return count

    @cached_property
    def hamming_width(self):
        return self.width + self.parity_bits

    @cached_property
    def code_width(self):
        return self.hamming_width + 1

    @cached_property
    def position_width(self):
        return (self.code_width - 1).bit_length()

    @cached_property
    def data_positions(self):
        return tuple(position for position in range(1, self.hamming_width + 1) if position.bit_count() != 1)

    @cached_property
    def widths(self):
        from ecc.transaction import INPUTS, OUTPUTS
        result = dict.fromkeys((*INPUTS, *OUTPUTS), 1)
        result.update(i_encode_data=self.width, o_decoded_data=self.width,
                      i_decode_codeword=self.code_width, o_encoded_codeword=self.code_width,
                      o_corrected_codeword=self.code_width, o_error_position=self.position_width,
                      o_syndrome=self.parity_bits)
        return result

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width)

    def role(self, bit):
        if bit == self.hamming_width:
            return 'overall'
        return 'hamming' if (bit + 1).bit_count() == 1 else 'data'
