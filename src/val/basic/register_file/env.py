"""Connect observed transactions to independent checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from register_file.agent import RegisterFileAgent
from register_file.coverage import RegisterFileCoverage
from register_file.scoreboard import RegisterFileScoreboard


class RegisterFileEnv(VerificationEnv):
    agent_type = RegisterFileAgent
    scoreboard_type = RegisterFileScoreboard
    coverage_type = RegisterFileCoverage
