"""Geometry and Python-only test settings; reuse the ECC reference contract."""
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
import os
from pathlib import Path
import sys
from cocotb.utils import get_time_from_sim_steps

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'basic'))
from ecc.config import EccConfig
from scratchpad_bank.transaction import PORTS

DEFAULTS = dict(DATA_WIDTH=128, DEPTH_WORDS=1024, TAG_WIDTH=8, MAX_OUTSTANDING=8,
                BACKEND_READ_LATENCY=1, PROTECTION_MODE=0, PARITY_GRANULARITY=8,
                SCRUB_ON_CORRECT=1, ASYNC_RESET=0)


@dataclass(frozen=True)
class ScratchpadBankConfig:
    parameters: dict
    seed: int
    random_cycles: int
    check_internals: bool
    coverage_file: Path
    probe: str

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('SCRATCHPAD_BANK_' + name, str(default)), 0)
        results = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/scratchpad_bank/results.xml'))
        flag = setting('CHECK_INTERNALS', 1)
        assert flag in (0, 1)
        c = cls({n: setting(n, d) for n, d in DEFAULTS.items()}, setting('SEED', 20261023),
                setting('RANDOM_CYCLES', 2000), bool(flag),
                Path(os.getenv('SCRATCHPAD_BANK_COVERAGE_FILE', str(results.with_name('coverage.json')))),
                os.getenv('SCRATCHPAD_BANK_ASSERTION_PROBE', ''))
        assert c.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0
        assert get_time_from_sim_steps(1, unit='ps') <= 1
        return c

    @cached_property
    def ecc(self):
        return EccConfig(self.DATA_WIDTH, self.seed, self.random_cycles, True, self.coverage_file)

    @property
    def instrumentation(self):
        flag = int(os.getenv('SCRATCHPAD_BANK_INSTRUMENTATION', '1'))
        assert flag in (0, 1)
        return bool(flag)

    @property
    def bytes(self):
        return self.DATA_WIDTH // 8

    @property
    def byte_log(self):
        return self.bytes.bit_length() - 1

    @property
    def stored_width(self):
        return (self.DATA_WIDTH if self.PROTECTION_MODE == 0 else
                self.DATA_WIDTH + self.DATA_WIDTH // self.PARITY_GRANULARITY if self.PROTECTION_MODE == 1
                else self.ecc.code_width)

    @property
    def mask_width(self):
        return self.bytes if self.PROTECTION_MODE == 0 else self.stored_width

    @property
    def aliases(self):
        return dict(D=self.DATA_WIDTH, B=self.bytes, T=self.TAG_WIDTH,
                    A=max(1, (self.DEPTH_WORDS * self.bytes - 1).bit_length()),
                    S=max(1, self.byte_log.bit_length()), O=self.MAX_OUTSTANDING.bit_length())

    @property
    def widths(self):
        return {n: self.aliases[w] if isinstance(w, str) else w for n, (_, w) in PORTS.items()}
