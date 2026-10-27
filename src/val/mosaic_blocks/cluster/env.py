"""Separate agent, passive scoreboard and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from cluster.agent import ClusterAgent
from cluster.scoreboard import ClusterScoreboard
from cluster.coverage import ClusterCoverage

class ClusterEnv(VerificationEnv):
    agent_type = ClusterAgent
    scoreboard_type = ClusterScoreboard
    coverage_type = ClusterCoverage
