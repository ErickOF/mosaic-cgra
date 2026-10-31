"""Shared UVM wiring keeps checking independent from stimulus."""

from mosaic_uvm.components import VerificationEnv
from configuration_network.agent import NetworkAgent
from configuration_network.scoreboard import NetworkScoreboard
from configuration_network.coverage import NetworkCoverage


class NetworkEnv(VerificationEnv):
    agent_type = NetworkAgent
    scoreboard_type = NetworkScoreboard
    coverage_type = NetworkCoverage
