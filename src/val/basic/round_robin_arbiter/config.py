"""Expected geometry, optional payload fixture and reproducible test settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

STALL_LIMIT = 8
LONG_STALL = 32
LOCK_LENGTHS = (1, 2, 8)
PAYLOAD_WIDTH = 32


@dataclass(frozen=True)
class ArbiterConfig:
    requesters: int
    initial: int
    has_lock: bool
    asynchronous: bool
    fixture: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('ROUND_ROBIN_ARBITER_' + name, str(default)), 0)
        lock, asynchronous, fixture, internal = (setting(name, default) for name, default in
            (('HAS_LOCK', 1), ('ASYNC_RESET', 0), ('PAYLOAD_FIXTURE', 0), ('CHECK_INTERNALS', 1)))
        assert all(value in (0, 1) for value in (lock, asynchronous, fixture, internal))
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/round_robin_arbiter/results.xml')).with_name('coverage.json')
        config = cls(setting('NUM_REQUESTERS', 4), setting('INITIAL_PRIORITY', 0), bool(lock), bool(asynchronous),
            bool(fixture), setting('SEED', 20261019), setting('RANDOM_CYCLES', 2000), bool(internal),
            os.getenv('ROUND_ROBIN_ARBITER_ASSERTION_PROBE', ''),
            Path(os.getenv('ROUND_ROBIN_ARBITER_COVERAGE_FILE', str(report))))
        assert config.requesters >= 1 and 0 <= config.initial < config.requesters and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for zero-delay RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def index_width(self):
        return max(1, (self.requesters-1).bit_length())

    @property
    def parameters(self):
        return dict(NUM_REQUESTERS=self.requesters, INITIAL_PRIORITY=self.initial,
            HAS_LOCK=int(self.has_lock), ASYNC_RESET=int(self.asynchronous))

    @property
    def widths(self):
        from round_robin_arbiter.transaction import INPUTS, OUTPUTS
        widths = dict.fromkeys((*INPUTS, *OUTPUTS), 1)
        widths.update(dict.fromkeys(('i_request', 'i_eligible', 'i_lock', 'o_grant_onehot'), self.requesters))
        widths.update(o_grant_index=self.index_width, o_lock_owner=self.index_width)
        if self.fixture:
            widths.update(i_payload=self.requesters*PAYLOAD_WIDTH, o_payload=PAYLOAD_WIDTH,
                o_received_valid=1, o_received_index=self.index_width, o_received_payload=PAYLOAD_WIDTH)
        return widths

    @property
    def inputs(self):
        return tuple(name for name in self.widths if name.startswith('i_'))

    @property
    def outputs(self):
        return tuple(name for name in self.widths if name.startswith('o_'))
