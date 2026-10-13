"""Static sequencer profiles and reproducible, four-state campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

from context_sequencer.constants import INPUTS, OUTPUTS


@dataclass(frozen=True)
class SequencerConfig:
    depth: int
    count_width: int
    loop: bool
    suspend: bool
    switch: bool
    async_reset: bool
    random_cycles: int
    seed: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        flags = [int(os.getenv(f"CONTEXT_SEQUENCER_{name}", default)) for name, default in (
            ("HAS_LOOP", "1"), ("HAS_SUSPEND", "1"), ("HAS_EXTERNAL_SWITCH", "1"), ("ASYNC_RESET", "0"), ("CHECK_INTERNALS", "1"))]
        assert set(flags) <= {0, 1}
        path = Path(os.getenv("COCOTB_RESULTS_FILE", "build/context_sequencer/results.xml")).with_name("coverage.json")
        config = cls(int(os.getenv("CONTEXT_SEQUENCER_CONTEXT_DEPTH", "4")),
                     int(os.getenv("CONTEXT_SEQUENCER_LOOP_COUNT_WIDTH", "16")), *map(bool, flags[:4]),
                     int(os.getenv("CONTEXT_SEQUENCER_RANDOM_CYCLES", "2000")),
                     int(os.getenv("CONTEXT_SEQUENCER_SEED", "20261012")), bool(flags[4]),
                     os.getenv("CONTEXT_SEQUENCER_ASSERTION_PROBE", ""),
                     Path(os.getenv("CONTEXT_SEQUENCER_COVERAGE_FILE", str(path))))
        assert config.depth >= 1 and config.count_width >= 1 and config.random_cycles >= 1000
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "Use TEST_SETTLE_NS=0 for zero-delay RTL"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Use 1 ps resolution or finer"
        return config

    @property
    def address_width(self):
        return max(1, (self.depth - 1).bit_length())

    @property
    def maximum_count(self):
        return (1 << self.count_width) - 1

    @property
    def parameters(self):
        return dict(CONTEXT_DEPTH=self.depth, LOOP_COUNT_WIDTH=self.count_width, HAS_LOOP=int(self.loop),
                    HAS_SUSPEND=int(self.suspend), HAS_EXTERNAL_SWITCH=int(self.switch), ASYNC_RESET=int(self.async_reset))

    @property
    def widths(self):
        widths = dict.fromkeys((*INPUTS, *OUTPUTS), 1)
        widths.update(dict.fromkeys(("i_start_context", "i_switch_context", "i_transition_target", "o_active_context",
                                    "o_candidate_context", "o_loop_owner"), self.address_width))
        widths.update(i_loop_count=self.count_width, o_loop_remaining=self.count_width, i_transition_mode=3, o_error_code=3)
        return widths
