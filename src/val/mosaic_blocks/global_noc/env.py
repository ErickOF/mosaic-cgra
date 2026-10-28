"""Agent, independent scoreboard and checked coverage."""
from mosaic_uvm.components import VerificationEnv
from global_noc.agent import NocAgent
from global_noc.scoreboard import NocScoreboard
from global_noc.coverage import NocCoverage
class NocEnv(VerificationEnv):
    agent_type=NocAgent
    scoreboard_type=NocScoreboard
    coverage_type=NocCoverage
