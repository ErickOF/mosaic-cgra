"""Reusable UVM agent composition."""

from mosaic_uvm.components import ActiveAgent
from tile_power_controller.driver import PowerDriver
from tile_power_controller.monitor import PowerMonitor


class PowerAgent(ActiveAgent):
    driver_type = PowerDriver
    monitor_type = PowerMonitor
