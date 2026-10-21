"""Keep stimulus, independent prediction, observations and coverage separate."""
from mosaic_uvm.components import VerificationEnv
from dot_product.agent import DotProductAgent
from dot_product.scoreboard import DotProductScoreboard
from dot_product.coverage import DotProductCoverage


class DotProductEnv(VerificationEnv):
    agent_type = DotProductAgent
    scoreboard_type = DotProductScoreboard
    coverage_type = DotProductCoverage
