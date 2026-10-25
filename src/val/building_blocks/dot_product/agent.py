"""Reuse the common UVM active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from dot_product.driver import DotProductDriver
from dot_product.monitor import DotProductMonitor


class DotProductAgent(ActiveAgent):
    driver_type = DotProductDriver
    monitor_type = DotProductMonitor
