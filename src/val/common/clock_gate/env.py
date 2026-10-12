"""ClockGate env components for specification-based PyUVM validation."""

from clock_gate.agent import ClockGateAgent
from clock_gate.coverage import ClockGateCoverage
from clock_gate.scoreboard import ClockGateScoreboard
from mosaic_uvm.components import VerificationEnv


class ClockGateEnv(VerificationEnv):
    agent_type = ClockGateAgent
    scoreboard_type = ClockGateScoreboard
    coverage_type = ClockGateCoverage
