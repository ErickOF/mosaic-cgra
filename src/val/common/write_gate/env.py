"""WriteGate env components for specification-based PyUVM validation."""

from mosaic_uvm.components import VerificationEnv
from write_gate.agent import WriteGateAgent
from write_gate.coverage import WriteGateCoverage
from write_gate.scoreboard import WriteGateScoreboard


class WriteGateEnv(VerificationEnv):
    agent_type = WriteGateAgent
    scoreboard_type = WriteGateScoreboard
    coverage_type = WriteGateCoverage
