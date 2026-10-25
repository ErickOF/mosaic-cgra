"""Keep stimulus, observations, independent prediction and coverage separate."""

from mosaic_uvm.components import VerificationEnv
from scalar_alu.agent import AluAgent
from scalar_alu.scoreboard import AluScoreboard
from scalar_alu.coverage import AluCoverage


class AluEnv(VerificationEnv):
    agent_type = AluAgent
    scoreboard_type = AluScoreboard
    coverage_type = AluCoverage
