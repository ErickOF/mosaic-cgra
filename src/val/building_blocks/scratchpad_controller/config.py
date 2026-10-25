"""Specification geometry and explicit simulator/test configuration."""
from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
from scratchpad_controller.transaction import PORTS

DEFAULTS = dict(DATA_WIDTH=128, NUM_BANKS=8, BANK_DEPTH_WORDS=1024, NUM_CLIENTS=4,
    CLIENT_TAG_WIDTH=8, MAX_OUTSTANDING_PER_CLIENT=8, INTERLEAVE_BYTES=16, MAP_MODE=0,
    ENFORCE_PERMISSIONS=1, DEFAULT_ALLOW=0, ASYNC_RESET=0)


@dataclass(frozen=True)
class ControllerConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path
    integration: bool = False
    protection: int = 0
    probe: str = ''

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, value):
            return int(os.getenv('SCRATCHPAD_CONTROLLER_' + name, str(value)), 0)
        result = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/scratchpad_controller/results.xml'))
        c = cls({k: setting(k, v) for k, v in DEFAULTS.items()}, setting('SEED', 20261023),
            setting('RANDOM_CYCLES', 2000), Path(os.getenv('SCRATCHPAD_CONTROLLER_COVERAGE_FILE',
            str(result.with_name('coverage.json')))), bool(setting('INTEGRATION', 0)),
            setting('PROTECTION', 0), os.getenv('SCRATCHPAD_CONTROLLER_PROBE', ''))
        assert c.random_cycles >= 1000
        return c

    @cached_property
    def instrumentation(self):
        flag = int(os.getenv('SCRATCHPAD_CONTROLLER_INSTRUMENTATION', '1'))
        assert flag in (0, 1)
        return bool(flag)

    @cached_property
    def bytes(self):
        return self.DATA_WIDTH // 8

    @cached_property
    def capacity(self):
        return self.bytes * self.NUM_BANKS * self.BANK_DEPTH_WORDS

    @cached_property
    def aliases(self):
        return dict(C=self.NUM_CLIENTS, B=self.NUM_BANKS, D=self.DATA_WIDTH, Y=self.bytes,
            P=self.NUM_CLIENTS * self.NUM_BANKS, T=self.CLIENT_TAG_WIDTH,
            A=max(1, (self.capacity - 1).bit_length()),
            L=max(1, (self.bytes * self.BANK_DEPTH_WORDS - 1).bit_length()),
            S=max(1, (self.bytes.bit_length() - 1).bit_length()),
            K=max(1, (self.NUM_CLIENTS - 1).bit_length()) + self.slot_width,
            O=self.MAX_OUTSTANDING_PER_CLIENT.bit_length())

    @cached_property
    def slot_width(self):
        return max(1, (self.MAX_OUTSTANDING_PER_CLIENT - 1).bit_length())

    @cached_property
    def widths(self):
        def width(w):
            if isinstance(w, tuple):
                return width(w[0]) * width(w[1])
            return self.aliases[w] if isinstance(w, str) else w
        return {n: width(w) for n, (_, w) in PORTS.items()}
