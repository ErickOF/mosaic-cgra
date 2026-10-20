"""Connect observed transactions to independent checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from vector_register_file.agent import VectorRegisterFileAgent
from vector_register_file.coverage import VectorRegisterFileCoverage
from vector_register_file.scoreboard import VectorRegisterFileScoreboard


class VectorRegisterFileEnv(VerificationEnv):
    agent_type = VectorRegisterFileAgent
    scoreboard_type = VectorRegisterFileScoreboard
    coverage_type = VectorRegisterFileCoverage
