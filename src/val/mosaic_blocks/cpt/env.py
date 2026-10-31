"""Connect independent scoreboards and checked coverage to the monitor."""
from mosaic_uvm.components import VerificationEnv
from cpt.agent import CptAgent
from cpt.coverage import CptCoverage
from cpt.scoreboard import CptScoreboard
class CptEnv(VerificationEnv):
    agent_type = CptAgent
    scoreboard_type = CptScoreboard
    coverage_type = CptCoverage
