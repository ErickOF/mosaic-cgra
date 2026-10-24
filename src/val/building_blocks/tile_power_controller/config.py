"""Parameters and widths shared by the public-port driver and model."""

from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
from tile_power_controller.transaction import PORTS

DEFAULTS = {
    'NUM_CLOCK_GROUPS': 4,
    'NUM_WAKE_SOURCES': 8,
    'NUM_STALL_REASONS': 4,
    'CONTEXT_ID_WIDTH': 8,
    'IDLE_ENTRY_CYCLES': 8,
    'MIN_IDLE_RESIDENCY_CYCLES': 2,
    'WAKEUP_STABILIZE_CYCLES': 2,
    'ISOLATION_SETUP_CYCLES': 2,
    'POWER_STABLE_CYCLES': 4,
    'RESET_HOLD_CYCLES': 4,
    'DRAIN_TIMEOUT_CYCLES': 1024,
    'ACK_TIMEOUT_CYCLES': 64,
    'POWER_TIMEOUT_CYCLES': 1024,
    'POWER_GOOD_SYNC_STAGES': 2,
    'SUPPORT_RETENTION': 0,
    'SUPPORT_POWER_GATING': 0,
    'WAKE_ON_EVENT': 1,
    'ASYNC_RESET': 0,
    'CLOCK_GROUP_ALWAYS_ON_MASK': 0,
    'WAKEUP_CLOCK_GROUP_MASK': 15,
}
TIMERS = {
    'idle': 'IDLE_ENTRY_CYCLES',
    'qualification': 'POWER_STABLE_CYCLES',
    'drain': 'DRAIN_TIMEOUT_CYCLES',
    'save': 'ACK_TIMEOUT_CYCLES',
    'restore': 'ACK_TIMEOUT_CYCLES',
    'power_up': 'POWER_TIMEOUT_CYCLES',
    'power_down': 'POWER_TIMEOUT_CYCLES',
    'isolation': 'ISOLATION_SETUP_CYCLES',
    'reset': 'RESET_HOLD_CYCLES',
    'wake': 'WAKEUP_STABILIZE_CYCLES',
}


@dataclass(frozen=True)
class PowerConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('TILE_POWER_CONTROLLER_' + name, str(default)), 0)

        results = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/tile_power_controller/results.xml'))
        c = cls(
            {n: setting(n, value) for n, value in DEFAULTS.items()},
            setting('SEED', 20261023),
            setting('RANDOM_CYCLES', 2000),
            Path(
                os.getenv(
                    'TILE_POWER_CONTROLLER_COVERAGE_FILE', str(results.with_name('coverage.json'))
                )
            ),
        )
        assert c.random_cycles >= 1000
        return c

    @cached_property
    def widths(self):
        aliases = dict(
            G=self.NUM_CLOCK_GROUPS,
            W=self.NUM_WAKE_SOURCES,
            S=self.NUM_STALL_REASONS,
            C=self.CONTEXT_ID_WIDTH,
            IW=self.IDLE_ENTRY_CYCLES.bit_length(),
            **{
                'tile_power_controller_pkg::POWER_STATE_WIDTH': 4,
                'tile_power_controller_pkg::POWER_COMMAND_WIDTH': 3,
                'tile_power_controller_pkg::POWER_ERROR_WIDTH': 4,
                'tile_power_controller_pkg::POWER_RESIDENCY_WIDTH': 32,
            },
        )
        return {n: w if isinstance(w, int) else aliases[w] for n, (_, w) in PORTS.items()}
