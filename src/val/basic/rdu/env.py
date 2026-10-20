"""Connect checked observations to independent models and coverage."""

from mosaic_uvm.components import VerificationEnv
from rdu.agent import RduAgent
from rdu.coverage import RduCoverage
from rdu.scoreboard import RduScoreboard


class RduEnv(VerificationEnv):
    agent_type = RduAgent
    scoreboard_type = RduScoreboard
    coverage_type = RduCoverage
