"""Reusable active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from bct.driver import BctDriver
from bct.monitor import BctMonitor
class BctAgent(ActiveAgent):
    driver_type = BctDriver
    monitor_type = BctMonitor
