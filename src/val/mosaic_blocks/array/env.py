"""Separate active agent, passive scoreboard and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from mosaic_blocks.array.agent import ArrayAgent
from mosaic_blocks.array.scoreboard import ArrayScoreboard
from mosaic_blocks.array.coverage import ArrayCoverage

class ArrayEnv(VerificationEnv):
    agent_type = ArrayAgent
    scoreboard_type = ArrayScoreboard
    coverage_type = ArrayCoverage
