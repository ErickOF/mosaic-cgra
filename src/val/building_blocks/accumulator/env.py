"""Connect checked observations to the separate model and coverage collector."""

from mosaic_uvm.components import VerificationEnv
from accumulator.agent import AccumulatorAgent
from accumulator.coverage import AccumulatorCoverage
from accumulator.scoreboard import AccumulatorScoreboard


class AccumulatorEnv(VerificationEnv):
    agent_type = AccumulatorAgent
    scoreboard_type = AccumulatorScoreboard
    coverage_type = AccumulatorCoverage
