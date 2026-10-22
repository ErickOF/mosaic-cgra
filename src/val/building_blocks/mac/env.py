"""Keep stimulus, independent prediction, observations and coverage separate."""
from mosaic_uvm.components import VerificationEnv
from mac.agent import MacAgent
from mac.scoreboard import MacScoreboard
from mac.coverage import MacCoverage


class MacEnv(VerificationEnv):
    agent_type = MacAgent
    scoreboard_type = MacScoreboard
    coverage_type = MacCoverage
