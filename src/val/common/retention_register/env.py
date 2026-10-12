"""Retention env components for specification-based PyUVM validation."""

from mosaic_uvm.components import VerificationEnv
from retention_register.agent import RetentionAgent
from retention_register.coverage import RetentionCoverage
from retention_register.scoreboard import RetentionScoreboard


class RetentionEnv(VerificationEnv):
    agent_type = RetentionAgent
    scoreboard_type = RetentionScoreboard
    coverage_type = RetentionCoverage
