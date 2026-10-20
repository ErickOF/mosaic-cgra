"""Connect observed requests/grants to independent checking and coverage."""
from mosaic_uvm.components import VerificationEnv
from round_robin_arbiter.agent import ArbiterAgent
from round_robin_arbiter.coverage import ArbiterCoverage
from round_robin_arbiter.scoreboard import ArbiterScoreboard


class ArbiterEnv(VerificationEnv):
    agent_type = ArbiterAgent
    scoreboard_type = ArbiterScoreboard
    coverage_type = ArbiterCoverage
