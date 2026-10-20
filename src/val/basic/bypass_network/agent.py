"""Active selection/capture agent with driver-coordinated monitoring."""

from mosaic_uvm.components import ActiveAgent
from bypass_network.driver import BypassNetworkDriver
from bypass_network.monitor import BypassNetworkMonitor


class BypassNetworkAgent(ActiveAgent):
    driver_type = BypassNetworkDriver
    monitor_type = BypassNetworkMonitor
