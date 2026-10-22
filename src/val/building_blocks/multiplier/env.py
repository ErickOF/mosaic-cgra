"""Keep stimulus, independent prediction, observations and coverage separate."""
from mosaic_uvm.components import VerificationEnv
from multiplier.agent import MultiplierAgent
from multiplier.scoreboard import MultiplierScoreboard
from multiplier.coverage import MultiplierCoverage


class MultiplierEnv(VerificationEnv):
    agent_type = MultiplierAgent
    scoreboard_type = MultiplierScoreboard
    coverage_type = MultiplierCoverage
