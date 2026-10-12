"""Counter env components for specification-based PyUVM validation."""

from counter.agent import CounterAgent
from counter.coverage import CounterCoverage
from counter.scoreboard import CounterScoreboard
from mosaic_uvm.components import VerificationEnv


class CounterEnv(VerificationEnv):
    agent_type = CounterAgent
    scoreboard_type = CounterScoreboard
    coverage_type = CounterCoverage
