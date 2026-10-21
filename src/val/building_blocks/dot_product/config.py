"""Expected elaboration, four-state precision and reproducible test settings."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from dot_product.transaction import INPUTS, OUTPUTS

DEFAULTS = dict(ELEMENT_WIDTH=8, NUM_TERMS=4, ACC_WIDTH=32, SUPPORT_ACCUMULATE=1,
                SUPPORT_SATURATION=1, LATENCY=2, MAX_LATENCY=8, ASYNC_RESET=0)


@dataclass(frozen=True)
class DotProductConfig:
    element: int
    terms: int
    width: int
    accumulate: int
    saturation: int
    latency: int
    maximum_latency: int
    asynchronous: int
    seed: int
    random_cycles: int
    check_internals: bool
    hdl_assertions: bool
    coverage_file: Path
    probe: str

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('DOT_PRODUCT_' + name, str(default)), 0)
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/dot_product/results.xml'))
        config = cls(*(setting(name, value) for name, value in DEFAULTS.items()),
                     setting('SEED', 20261020), setting('RANDOM_CYCLES', 2000),
                     bool(setting('CHECK_INTERNALS', 1)), bool(setting('HDL_ASSERTIONS', 1)),
                     Path(os.getenv('DOT_PRODUCT_COVERAGE_FILE', str(path.with_name('coverage.json')))),
                     os.getenv('DOT_PRODUCT_ASSERTION_PROBE', ''))
        assert config.element >= 1 and config.terms >= 1
        assert config.width >= config.reduction_width
        assert 0 <= config.latency <= config.maximum_latency
        assert set((config.accumulate, config.saturation, config.asynchronous)) <= {0, 1}
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL'
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return config

    @property
    def parameters(self):
        return dict(zip(DEFAULTS, (self.element, self.terms, self.width, self.accumulate,
                                  self.saturation, self.latency, self.maximum_latency,
                                  self.asynchronous), strict=True))

    @property
    def reduction_width(self):
        return 2 * self.element + (self.terms - 1).bit_length()

    @property
    def count_width(self):
        return self.terms.bit_length()

    @property
    def mask(self):
        return (1 << self.terms) - 1

    @property
    def word_mask(self):
        return (1 << self.element) - 1

    @property
    def result_mask(self):
        return (1 << self.width) - 1

    @property
    def widths(self):
        result = dict.fromkeys((*INPUTS, *OUTPUTS), 1)
        result.update(i_term_mask=self.terms, i_operand_a=self.element * self.terms,
                      i_operand_b=self.element * self.terms, i_accumulator=self.width,
                      o_result=self.width, o_active_count=self.count_width)
        return result
