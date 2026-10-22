"""Reuse the common UVM active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from mac.driver import MacDriver
from mac.monitor import MacMonitor


class MacAgent(ActiveAgent):
    driver_type = MacDriver
    monitor_type = MacMonitor
