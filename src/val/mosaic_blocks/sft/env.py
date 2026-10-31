"""Connect independent scoreboards and checked coverage to the monitor."""
from mosaic_uvm.components import VerificationEnv
from sft.agent import SftAgent
from sft.coverage import SftCoverage
from sft.scoreboard import SftScoreboard
class SftEnv(VerificationEnv):
    agent_type = SftAgent
    scoreboard_type = SftScoreboard
    coverage_type = SftCoverage
