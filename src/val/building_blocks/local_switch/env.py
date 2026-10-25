"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from local_switch.agent import LocalSwitchAgent
from local_switch.coverage import LocalSwitchCoverage
from local_switch.scoreboard import LocalSwitchScoreboard


class LocalSwitchEnv(VerificationEnv):
    agent_type = LocalSwitchAgent
    scoreboard_type = LocalSwitchScoreboard
    coverage_type = LocalSwitchCoverage
