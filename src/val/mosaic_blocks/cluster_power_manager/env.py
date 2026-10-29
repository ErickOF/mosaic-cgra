"""Standard UVM agent, scoreboard and independent coverage collector."""
from mosaic_uvm.components import VerificationEnv
from cluster_power_manager.agent import PowerAgent
from cluster_power_manager.scoreboard import PowerScoreboard
from cluster_power_manager.coverage import PowerCoverage


class PowerEnv(VerificationEnv):
    agent_type = PowerAgent
    scoreboard_type = PowerScoreboard
    coverage_type = PowerCoverage
