"""Dff env components for specification-based PyUVM validation."""

from dff.agent import DffAgent
from dff.coverage import DffCoverage
from dff.scoreboard import DffScoreboard
from mosaic_uvm.components import VerificationEnv


class DffEnv(VerificationEnv):
    agent_type = DffAgent
    scoreboard_type = DffScoreboard
    coverage_type = DffCoverage
