"""Conventional active PyUVM agent, using shared construction and wiring."""
from mosaic_uvm.components import ActiveAgent
from cluster.driver import ClusterDriver
from cluster.monitor import ClusterMonitor

class ClusterAgent(ActiveAgent):
    driver_type = ClusterDriver
    monitor_type = ClusterMonitor
