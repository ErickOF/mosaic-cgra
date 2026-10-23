"""Keep stimulus, independent prediction, observations and coverage separate."""

from mosaic_uvm.components import VerificationEnv
from noc_router.agent import RouterAgent
from noc_router.scoreboard import RouterScoreboard
from noc_router.coverage import RouterCoverage


class RouterEnv(VerificationEnv):
    agent_type = RouterAgent
    scoreboard_type = RouterScoreboard
    coverage_type = RouterCoverage
