"""Active command/activity/physical-status agent."""
from mosaic_uvm.components import ActiveAgent
from cluster_power_manager.driver import PowerDriver
from cluster_power_manager.monitor import PowerMonitor


class PowerAgent(ActiveAgent):
    driver_type = PowerDriver
    monitor_type = PowerMonitor
