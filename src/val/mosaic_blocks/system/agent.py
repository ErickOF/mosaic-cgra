"""Reuse released synchronous driver/monitor with system-specific transactions."""
from mosaic_uvm.components import ActiveAgent
from cluster.driver import ClusterDriver
from cluster.monitor import ClusterMonitor

class SystemAgent(ActiveAgent):
    driver_type = ClusterDriver
    monitor_type = ClusterMonitor
