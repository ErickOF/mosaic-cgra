"""Conventional active agent reusing the shared clock driver and public monitor."""
from mosaic_uvm.components import ActiveAgent
from cluster.driver import ClusterDriver
from cluster.monitor import ClusterMonitor

class ArrayAgent(ActiveAgent):
    driver_type = ClusterDriver
    monitor_type = ClusterMonitor
