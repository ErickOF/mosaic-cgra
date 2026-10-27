"""Active request agent with passive endpoint observation."""

from mosaic_uvm.components import ActiveAgent
from configuration_network.driver import NetworkDriver
from configuration_network.monitor import NetworkMonitor


class NetworkAgent(ActiveAgent):
    driver_type = NetworkDriver
    monitor_type = NetworkMonitor
