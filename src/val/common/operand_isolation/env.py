"""OperandIsolation env components for specification-based PyUVM validation."""

from mosaic_uvm.components import VerificationEnv
from operand_isolation.agent import OperandIsolationAgent
from operand_isolation.coverage import OperandIsolationCoverage
from operand_isolation.scoreboard import OperandIsolationScoreboard


class OperandIsolationEnv(VerificationEnv):
    agent_type = OperandIsolationAgent
    scoreboard_type = OperandIsolationScoreboard
    coverage_type = OperandIsolationCoverage
