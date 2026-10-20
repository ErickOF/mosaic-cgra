"""Connect observed signals to independent queue checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from skid_buffer.agent import SkidBufferAgent
from skid_buffer.coverage import SkidBufferCoverage
from skid_buffer.scoreboard import SkidBufferScoreboard


class SkidBufferEnv(VerificationEnv):
    agent_type = SkidBufferAgent
    scoreboard_type = SkidBufferScoreboard
    coverage_type = SkidBufferCoverage
