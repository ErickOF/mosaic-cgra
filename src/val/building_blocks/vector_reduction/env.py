"""Keep observations, independent checking, coverage and stimulus separate."""

from mosaic_uvm.components import VerificationEnv

from vector_reduction.agent import ReductionAgent
from vector_reduction.coverage import ReductionCoverage
from vector_reduction.scoreboard import ReductionScoreboard


class ReductionEnv(VerificationEnv):
    agent_type = ReductionAgent
    scoreboard_type = ReductionScoreboard
    coverage_type = ReductionCoverage
