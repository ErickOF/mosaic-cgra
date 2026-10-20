"""Connect observed signals to independent queue checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from register_slice.agent import RegisterSliceAgent
from register_slice.coverage import RegisterSliceCoverage
from register_slice.scoreboard import RegisterSliceScoreboard


class RegisterSliceEnv(VerificationEnv):
    agent_type = RegisterSliceAgent
    scoreboard_type = RegisterSliceScoreboard
    coverage_type = RegisterSliceCoverage
