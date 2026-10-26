"""Agent, passive scoreboard, and independent checked coverage."""

from mosaic_uvm.components import VerificationEnv
from static_mesh.agent import MeshAgent
from static_mesh.scoreboard import MeshScoreboard
from static_mesh.coverage import MeshCoverage


class MeshEnv(VerificationEnv):
    agent_type = MeshAgent
    scoreboard_type = MeshScoreboard
    coverage_type = MeshCoverage
