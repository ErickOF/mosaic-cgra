"""Reusable active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from cpt.driver import CptDriver
from cpt.monitor import CptMonitor
class CptAgent(ActiveAgent):
    driver_type = CptDriver
    monitor_type = CptMonitor
