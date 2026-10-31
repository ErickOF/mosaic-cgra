"""Reusable active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from mst.driver import MstDriver
from mst.monitor import MstMonitor
class MstAgent(ActiveAgent):
    driver_type = MstDriver
    monitor_type = MstMonitor
