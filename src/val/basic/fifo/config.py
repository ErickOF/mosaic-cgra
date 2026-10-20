"""Expected elaborated geometry and reproducible simulation settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class FifoConfig:
    width: int
    depth: int
    asynchronous: bool
    almost_full: int
    almost_empty: int
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('FIFO_' + name, str(default)))
        depth = setting('DEPTH', 4)
        asynchronous, internals = setting('ASYNC_RESET', 0), setting('CHECK_INTERNALS', 1)
        assert asynchronous in (0, 1) and internals in (0, 1)
        default_report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/fifo/results.xml')).with_name('coverage.json')
        config = cls(setting('DATA_WIDTH', 32), depth, bool(asynchronous),
                     setting('ALMOST_FULL_LEVEL', depth - 1 if depth > 1 else 1),
                     setting('ALMOST_EMPTY_LEVEL', 1 if depth > 1 else 0),
                     setting('SEED', 20261013), setting('RANDOM_CYCLES', 2000), bool(internals),
                     os.getenv('FIFO_ASSERTION_PROBE', ''),
                     Path(os.getenv('FIFO_COVERAGE_FILE', str(default_report))))
        assert config.width >= 1 and depth >= 1
        assert 1 <= config.almost_full <= depth and 0 <= config.almost_empty < depth
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for this zero-delay RTL suite'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, DEPTH=self.depth, ASYNC_RESET=int(self.asynchronous),
                    ALMOST_FULL_LEVEL=self.almost_full, ALMOST_EMPTY_LEVEL=self.almost_empty)

    @property
    def widths(self):
        from fifo.transaction import INPUTS, OUTPUTS
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | dict(
            i_data=self.width, o_data=self.width, o_occupancy=self.depth.bit_length())

    @property
    def pointer_width(self):
        return max(1, (self.depth - 1).bit_length())
