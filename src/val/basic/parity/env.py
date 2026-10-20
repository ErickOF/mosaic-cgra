"""Connect real observations to independent checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from parity.agent import ParityAgent
from parity.coverage import ParityCoverage
from parity.scoreboard import ParityScoreboard


class ParityEnv(VerificationEnv):
    agent_type = ParityAgent
    scoreboard_type = ParityScoreboard
    coverage_type = ParityCoverage
