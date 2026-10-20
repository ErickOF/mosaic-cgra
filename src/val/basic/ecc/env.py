"""Connect the codec agent, independent scoreboard and coverage collector."""

from mosaic_uvm.components import VerificationEnv
from ecc.agent import EccAgent
from ecc.coverage import EccCoverage
from ecc.scoreboard import EccScoreboard


class EccEnv(VerificationEnv):
    agent_type=EccAgent
    scoreboard_type=EccScoreboard
    coverage_type=EccCoverage
