"""Expected hardware geometry and reproducible Python-only simulation settings."""
from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
from rsqrt_unit.defaults import DEFAULTS
from rsqrt_unit.ports import PORTS


@dataclass(frozen=True)
class RsqrtConfig:
    parameters: dict[str, int]
    seed: int
    random_cycles: int
    coverage_file: Path

    def __getattr__(self, name):
        if name in self.parameters:
            return self.parameters[name]
        raise AttributeError(name)

    @classmethod
    def from_environment(cls):
        def get(name, default):
            return int(os.getenv('RSQRT_UNIT_' + name, str(default)), 0)
        output = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/rsqrt_unit/results.xml'))
        c = cls({k: get(k, v) for k, v in DEFAULTS.items()}, get('SEED', 20261025),
                get('RANDOM_CYCLES', 2000), Path(os.getenv(
                    'RSQRT_UNIT_COVERAGE_FILE', str(output.with_name('coverage.json')))))
        assert c.random_cycles >= 1000
        return c

    @cached_property
    def widths(self):
        derived = self.parameters | dict(
            ITERATION_WIDTH=max(1, self.MAX_ITERATIONS.bit_length()),
            OUTPUT_QUEUE_OCCUPANCY_WIDTH=self.OUTPUT_QUEUE_DEPTH.bit_length())
        return {name: width if isinstance(width, int) else
                eval(width, {'__builtins__': {}}, derived)
                for name, (_, width) in PORTS.items()}

    @property
    def latency(self):
        return 4 + 3 * self.MAX_ITERATIONS

    @property
    def lanes(self):
        return self.latency if self.EVALUATION_ARCH else 1

    @property
    def seed_lane(self):
        return 2 if self.EVALUATION_ARCH else 0
