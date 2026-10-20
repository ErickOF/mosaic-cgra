"""Connect checked observations to independent models and coverage."""

from mosaic_uvm.components import VerificationEnv
from performance_counters.agent import PerformanceCountersAgent
from performance_counters.coverage import PerformanceCountersCoverage
from performance_counters.scoreboard import PerformanceCountersScoreboard


class PerformanceCountersEnv(VerificationEnv):
    agent_type = PerformanceCountersAgent
    scoreboard_type = PerformanceCountersScoreboard
    coverage_type = PerformanceCountersCoverage
