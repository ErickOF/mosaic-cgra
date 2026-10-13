"""Connect the routing agent, independent reference, and mandatory coverage."""

from mosaic_uvm.components import VerificationEnv
from bypass_network.agent import BypassNetworkAgent
from bypass_network.coverage import BypassNetworkCoverage
from bypass_network.scoreboard import BypassNetworkScoreboard


class BypassNetworkEnv(VerificationEnv):
    agent_type = BypassNetworkAgent
    scoreboard_type = BypassNetworkScoreboard
    coverage_type = BypassNetworkCoverage
