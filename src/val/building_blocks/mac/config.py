"""Elaboration expectations and reproducible simulation settings."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from mac.transaction import INPUTS, OUTPUTS

DEFAULTS = dict(OPERAND_WIDTH=8, ACC_WIDTH=32, SUPPORT_SATURATION=1,
                LATENCY=1, MAX_LATENCY=4, ASYNC_RESET=0)


@dataclass(frozen=True)
class MacConfig:
    operand: int
    width: int
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
            return int(os.getenv('MAC_' + name, str(default)), 0)
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/mac/results.xml'))
        config = cls(*(setting(name, value) for name, value in DEFAULTS.items()),
                     setting('SEED', 20261022), setting('RANDOM_CYCLES', 2000),
                     bool(setting('CHECK_INTERNALS', 1)), bool(setting('HDL_ASSERTIONS', 1)),
                     Path(os.getenv('MAC_COVERAGE_FILE', str(path.with_name('coverage.json')))),
                     os.getenv('MAC_ASSERTION_PROBE', ''))
        assert config.operand >= 1 and config.width >= 2 * config.operand
        assert 0 <= config.latency <= config.maximum_latency and config.maximum_latency >= 1
        assert set((config.saturation, config.asynchronous)) <= {0, 1}
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL'
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return config

    @property
    def parameters(self):
        return dict(zip(DEFAULTS, (self.operand, self.width, self.saturation, self.latency,
                                  self.maximum_latency, self.asynchronous), strict=True))

    @property
    def operand_mask(self):
        return (1 << self.operand) - 1

    @property
    def result_mask(self):
        return (1 << self.width) - 1

    @property
    def widths(self):
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | dict(
            i_operand_a=self.operand, i_operand_b=self.operand,
            i_accumulator=self.width, o_result=self.width)

    @property
    def contract(self):
        """Publish numerical/timing metadata without assuming an external package."""
        return dict(operation='integer_multiply_add', persistent_state=False,
                    operand_width=self.operand, product_width=2 * self.operand,
                    accumulator_width=self.width, signedness='uniform_per_operation',
                    arithmetic='exact_product_then_modular_or_saturating_add', rounding='none',
                    latency_enabled_edges=self.latency, initiation_interval_enabled_edges=1,
                    shared_clock_enable=bool(self.latency),
                    conservative_unsigned_count=((1 << self.width) - 1) // self.operand_mask ** 2,
                    conservative_signed_positive_count=((1 << (self.width - 1)) - 1) //
                        (1 << (2 * self.operand - 2)),
                    implementation='dot_product_NUM_TERMS_1_SUPPORT_ACCUMULATE_1',
                    physical_timing='NOT_RUN', physical_power='NOT_RUN')
