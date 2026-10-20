"""Expected elaboration geometry and reproducible verification settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class PerformanceCountersConfig:
    width: int
    counters: int
    events: int
    increment_width: int
    saturate: bool
    snapshot: bool
    threshold: bool
    asynchronous: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('PERFORMANCE_COUNTERS_' + name, str(default)))
        flags = [setting(name, default) for name, default in (
            ('SATURATE', 1), ('HAS_SNAPSHOT', 1), ('HAS_THRESHOLD', 1), ('ASYNC_RESET', 0), ('CHECK_INTERNALS', 1))]
        assert all(flag in (0, 1) for flag in flags)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/performance_counters/results.xml')).with_name('coverage.json')
        config = cls(setting('COUNTER_WIDTH', 48), setting('NUM_COUNTERS', 10), setting('NUM_EVENTS', 16),
            setting('INCREMENT_WIDTH', 16), *(bool(flag) for flag in flags[:4]),
            setting('SEED', 20261013), setting('RANDOM_CYCLES', 2000), bool(flags[4]),
            os.getenv('PERFORMANCE_COUNTERS_ASSERTION_PROBE', ''),
            Path(os.getenv('PERFORMANCE_COUNTERS_COVERAGE_FILE', str(report))))
        assert min(config.width, config.counters, config.events, config.increment_width) >= 1
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for this zero-delay RTL suite'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def parameters(self):
        return dict(COUNTER_WIDTH=self.width, NUM_COUNTERS=self.counters, NUM_EVENTS=self.events,
            INCREMENT_WIDTH=self.increment_width, SATURATE=int(self.saturate), HAS_SNAPSHOT=int(self.snapshot),
            HAS_THRESHOLD=int(self.threshold), ASYNC_RESET=int(self.asynchronous))

    @property
    def counter_address_width(self):
        return max(1, (self.counters - 1).bit_length())

    @property
    def event_address_width(self):
        return max(1, (self.events - 1).bit_length())

    @property
    def maximum(self):
        return (1 << self.width) - 1

    @property
    def increment_maximum(self):
        return (1 << self.increment_width) - 1

    @property
    def boundary_feasible(self):
        # Never deposit/force state to manufacture a wide-counter boundary hit.
        return self.maximum // self.increment_maximum <= 64

    @property
    def widths(self):
        from performance_counters.transaction import INPUTS, OUTPUTS
        return dict.fromkeys((*INPUTS, *OUTPUTS), 1) | dict(
            i_counter_enable=self.counters, i_clear=self.counters,
            i_event_select=self.counters*self.event_address_width, i_event_valid=self.events,
            i_event_increment=self.events*self.increment_width, i_threshold_enable=self.counters,
            i_threshold_value=self.counters*self.width, i_read_index=self.counter_address_width,
            o_read_data=self.width, o_counter_overflow=self.counters,
            o_threshold_event=self.counters, o_config_error=self.counters)
