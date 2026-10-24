"""Shared UVM wiring with controller-specific scoreboarding and coverage."""
from mosaic_uvm.components import VerificationEnv
from scratchpad_controller.agent import ControllerAgent
from scratchpad_controller.scoreboard import ControllerScoreboard
from scratchpad_controller.coverage import ControllerCoverage


class ControllerEnv(VerificationEnv):
    agent_type = ControllerAgent
    scoreboard_type = ControllerScoreboard
    coverage_type = ControllerCoverage
