"""ResetSynchronizer env components for specification-based PyUVM validation."""

from mosaic_uvm.components import VerificationEnv
from reset_synchronizer.agent import ResetSynchronizerAgent
from reset_synchronizer.coverage import ResetSynchronizerCoverage
from reset_synchronizer.scoreboard import ResetSynchronizerScoreboard


class ResetSynchronizerEnv(VerificationEnv):
    agent_type = ResetSynchronizerAgent
    scoreboard_type = ResetSynchronizerScoreboard
    coverage_type = ResetSynchronizerCoverage
