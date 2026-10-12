"""LevelShifter env components for specification-based PyUVM validation."""

from level_shifter.agent import LevelShifterAgent
from level_shifter.coverage import LevelShifterCoverage
from level_shifter.scoreboard import LevelShifterScoreboard
from mosaic_uvm.components import VerificationEnv


class LevelShifterEnv(VerificationEnv):
    agent_type = LevelShifterAgent
    scoreboard_type = LevelShifterScoreboard
    coverage_type = LevelShifterCoverage
