"""Connect independent scoreboards and checked coverage to the monitor."""
from mosaic_uvm.components import VerificationEnv
from bct.agent import BctAgent
from bct.coverage import BctCoverage
from bct.scoreboard import BctScoreboard
class BctEnv(VerificationEnv):
    agent_type = BctAgent
    scoreboard_type = BctScoreboard
    coverage_type = BctCoverage
