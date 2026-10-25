"""Connect the active agent, independent scoreboard and coverage collector."""

from mosaic_uvm.components import VerificationEnv
from tile_power_controller.agent import PowerAgent
from tile_power_controller.coverage import PowerCoverage
from tile_power_controller.scoreboard import PowerScoreboard


class PowerEnv(VerificationEnv):
    agent_type = PowerAgent
    scoreboard_type = PowerScoreboard
    coverage_type = PowerCoverage
