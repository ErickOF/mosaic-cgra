"""Connect independently observed traffic to the scoreboard and coverage."""
from mosaic_uvm.components import VerificationEnv
from loop_controller.agent import LoopControllerAgent
from loop_controller.coverage import LoopControllerCoverage
from loop_controller.scoreboard import LoopControllerScoreboard


class LoopControllerEnv(VerificationEnv):
    agent_type = LoopControllerAgent
    scoreboard_type = LoopControllerScoreboard
    coverage_type = LoopControllerCoverage
