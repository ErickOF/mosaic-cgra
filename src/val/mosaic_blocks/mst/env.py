"""Connect independent scoreboards and checked coverage to the monitor."""
from mosaic_uvm.components import VerificationEnv
from mst.agent import MstAgent
from mst.coverage import MstCoverage
from mst.scoreboard import MstScoreboard
class MstEnv(VerificationEnv):
    agent_type = MstAgent
    scoreboard_type = MstScoreboard
    coverage_type = MstCoverage
