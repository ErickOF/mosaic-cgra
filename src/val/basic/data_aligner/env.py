"""Wire the agent, independent scoreboard and coverage collector."""

from mosaic_uvm.components import VerificationEnv
from data_aligner.agent import AlignerAgent
from data_aligner.coverage import AlignerCoverage
from data_aligner.scoreboard import AlignerScoreboard


class AlignerEnv(VerificationEnv):
    agent_type = AlignerAgent
    coverage_type = AlignerCoverage
    scoreboard_type = AlignerScoreboard
