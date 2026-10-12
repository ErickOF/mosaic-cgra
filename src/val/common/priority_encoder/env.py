"""PriorityEncoder env components for specification-based PyUVM validation."""

from mosaic_uvm.components import VerificationEnv
from priority_encoder.agent import PriorityEncoderAgent
from priority_encoder.coverage import PriorityEncoderCoverage
from priority_encoder.scoreboard import PriorityEncoderScoreboard


class PriorityEncoderEnv(VerificationEnv):
    agent_type = PriorityEncoderAgent
    scoreboard_type = PriorityEncoderScoreboard
    coverage_type = PriorityEncoderCoverage
