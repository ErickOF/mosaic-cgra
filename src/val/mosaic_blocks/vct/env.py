"""Connect independent scoreboards and checked coverage to the monitor."""
from mosaic_uvm.components import VerificationEnv
from vct.agent import VctAgent
from vct.coverage import VctCoverage
from vct.scoreboard import VctScoreboard
class VctEnv(VerificationEnv):
    agent_type = VctAgent
    scoreboard_type = VctScoreboard
    coverage_type = VctCoverage
