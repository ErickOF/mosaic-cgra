"""Reusable active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from vct.driver import VctDriver
from vct.monitor import VctMonitor
class VctAgent(ActiveAgent):
    driver_type = VctDriver
    monitor_type = VctMonitor
