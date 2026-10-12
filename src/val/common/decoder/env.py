"""Decoder env components for specification-based PyUVM validation."""

from decoder.agent import DecoderAgent
from decoder.coverage import DecoderCoverage
from decoder.scoreboard import DecoderScoreboard
from mosaic_uvm.components import VerificationEnv


class DecoderEnv(VerificationEnv):
    agent_type = DecoderAgent
    scoreboard_type = DecoderScoreboard
    coverage_type = DecoderCoverage
