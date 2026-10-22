"""Reuse the common UVM active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from multiplier.driver import MultiplierDriver
from multiplier.monitor import MultiplierMonitor


class MultiplierAgent(ActiveAgent):
    driver_type = MultiplierDriver
    monitor_type = MultiplierMonitor
