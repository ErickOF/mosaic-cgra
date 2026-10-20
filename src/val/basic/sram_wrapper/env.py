"""Connect observed signals to independent queue checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from sram_wrapper.agent import SramAgent
from sram_wrapper.coverage import SramCoverage
from sram_wrapper.scoreboard import SramScoreboard


class SramEnv(VerificationEnv):
    agent_type = SramAgent
    scoreboard_type = SramScoreboard
    coverage_type = SramCoverage
