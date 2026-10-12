"""LaneMask env components for specification-based PyUVM validation."""

from lane_mask.agent import LaneMaskAgent
from lane_mask.coverage import LaneMaskCoverage
from lane_mask.scoreboard import LaneMaskScoreboard
from mosaic_uvm.components import VerificationEnv


class LaneMaskEnv(VerificationEnv):
    agent_type = LaneMaskAgent
    scoreboard_type = LaneMaskScoreboard
    coverage_type = LaneMaskCoverage
