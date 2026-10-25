"""Elaborated parameters and deterministic campaign settings."""
from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
from loop_controller.transaction import PORTS

DEFAULTS = dict(MAX_LOOP_DEPTH=4, INDEX_WIDTH=32, TRIP_COUNT_WIDTH=32,
    LINEAR_COUNT_WIDTH=64, II_WIDTH=8, CONTEXT_ID_WIDTH=8, RUN_ID_WIDTH=8,
    NUM_EVENTS=16, CONFIG_EPOCH_WIDTH=2, SUPPORT_BOUNDED_MODE=1,
    SUPPORT_SUSPEND=1, SUPPORT_ABORT=1, PROTECT_STATE=0, ASYNC_RESET=0)


@dataclass(frozen=True)
class LoopControllerConfig:
    parameters: dict
    seed: int
    random_cycles: int
    hdl_assertions: bool
    check_internals: bool
    coverage_file: Path

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('LOOP_CONTROLLER_' + name, str(default)), 0)
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/loop_controller/results.xml'))
        c = cls({n: setting(n, d) for n, d in DEFAULTS.items()}, setting('SEED', 20261022),
            setting('RANDOM_CYCLES', 2000), bool(setting('HDL_ASSERTIONS', 0)),
            bool(setting('CHECK_INTERNALS', 1)),
            Path(os.getenv('LOOP_CONTROLLER_COVERAGE_FILE', str(path.with_name('coverage.json')))))
        assert c.random_cycles >= 1000
        return c

    @cached_property
    def aliases(self):
        d = self.MAX_LOOP_DEPTH
        return dict(D=d, I=self.INDEX_WIDTH, T=self.TRIP_COUNT_WIDTH,
            L=self.LINEAR_COUNT_WIDTH, P=self.II_WIDTH, C=self.CONTEXT_ID_WIDTH,
            R=self.RUN_ID_WIDTH, E=self.CONFIG_EPOCH_WIDTH,
            DEPTH_WIDTH=d.bit_length(), EVENT_ID_WIDTH=max(1, (self.NUM_EVENTS - 1).bit_length()),
            INDEX_VECTOR_WIDTH=d*self.INDEX_WIDTH, TRIP_VECTOR_WIDTH=d*self.TRIP_COUNT_WIDTH,
            MODE_WIDTH=2, COMPARE_WIDTH=3, CONTROL_WIDTH=2,
            **{'loop_controller_pkg::COMPLETION_WIDTH': 2, 'loop_controller_pkg::ERROR_WIDTH': 5})

    @cached_property
    def widths(self):
        def width(w):
            if isinstance(w, int):
                return w
            result = 1
            for factor in w.split('*'):
                result *= self.aliases[factor]
            return result
        return {n: width(w) for n, (_, w) in PORTS.items()}
