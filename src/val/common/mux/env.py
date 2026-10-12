"""Mux env components for specification-based PyUVM validation."""

from mosaic_uvm.components import VerificationEnv
from mux.agent import MuxAgent
from mux.coverage import MuxCoverage
from mux.scoreboard import MuxScoreboard


class MuxEnv(VerificationEnv):
    agent_type = MuxAgent
    scoreboard_type = MuxScoreboard
    coverage_type = MuxCoverage
