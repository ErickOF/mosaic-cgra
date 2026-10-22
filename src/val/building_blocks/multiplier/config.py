"""Elaboration expectations and reproducible multiplier simulation settings."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from multiplier.transaction import INPUTS, OUTPUTS

DEFAULTS = dict(OPERAND_WIDTH=32, LATENCY=1, MAX_LATENCY=4, ASYNC_RESET=0)


@dataclass(frozen=True)
class MultiplierConfig:
    operand: int
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
            return int(os.getenv('MULTIPLIER_' + name, str(default)), 0)
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/multiplier/results.xml'))
        c = cls(*(setting(name, value) for name, value in DEFAULTS.items()),
                setting('SEED', 20261022), setting('RANDOM_CYCLES', 2000),
                bool(setting('CHECK_INTERNALS', 1)), bool(setting('HDL_ASSERTIONS', 1)),
                Path(os.getenv('MULTIPLIER_COVERAGE_FILE', str(path.with_name('coverage.json')))),
                os.getenv('MULTIPLIER_ASSERTION_PROBE', ''))
        assert c.operand >= 1 and c.maximum_latency >= 1
        assert 0 <= c.latency <= c.maximum_latency and c.asynchronous in (0, 1)
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL'
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return c

    @property
    def parameters(self):
        return dict(zip(DEFAULTS, (self.operand, self.latency, self.maximum_latency,
                                  self.asynchronous), strict=True))

    @property
    def operand_mask(self):
        return (1 << self.operand) - 1

    @property
    def product_width(self):
        return 2 * self.operand

    @property
    def widths(self):
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | dict(
            i_operand_a=self.operand, i_operand_b=self.operand, o_product=self.product_width)

    @property
    def contract(self):
        return dict(operation='scalar_integer_multiply', operand_width=self.operand,
                    product_width=self.product_width, signedness='independent_per_operand',
                    product_signed='signed_a_OR_signed_b', arithmetic='exact_full_product',
                    narrowing='none', rounding='none', saturation='none', persistent_state=False,
                    latency_enabled_edges=self.latency, initiation_interval_enabled_edges=1,
                    implementation='inferred_signed_W_plus_1_multiplier_and_response_registers',
                    reset='asynchronous' if self.asynchronous else 'synchronous',
                    physical_timing='NOT_RUN', physical_power='NOT_RUN')
