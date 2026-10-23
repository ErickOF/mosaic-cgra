"""Keep observations, independent checking, coverage and stimulus separate."""

from mosaic_uvm.components import VerificationEnv

from vector_lane.agent import LaneAgent
from vector_lane.coverage import LaneCoverage
from vector_lane.scoreboard import LaneScoreboard


class LaneEnv(VerificationEnv):
    agent_type = LaneAgent
    scoreboard_type = LaneScoreboard
    coverage_type = LaneCoverage
