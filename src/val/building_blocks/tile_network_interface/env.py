"""Connect the active agent, independent scoreboard and coverage collector."""

from mosaic_uvm.components import VerificationEnv
from tile_network_interface.agent import InterfaceAgent
from tile_network_interface.coverage import InterfaceCoverage
from tile_network_interface.scoreboard import InterfaceScoreboard


class InterfaceEnv(VerificationEnv):
    agent_type = InterfaceAgent
    scoreboard_type = InterfaceScoreboard
    coverage_type = InterfaceCoverage
