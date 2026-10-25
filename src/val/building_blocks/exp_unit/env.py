"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from exp_unit.agent import ExpUnitAgent
from exp_unit.coverage import ExpUnitCoverage
from exp_unit.scoreboard import ExpUnitScoreboard


class ExpUnitEnv(VerificationEnv):
    agent_type = ExpUnitAgent
    scoreboard_type = ExpUnitScoreboard
    coverage_type = ExpUnitCoverage
