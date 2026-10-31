"""Reusable active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from sft.driver import SftDriver
from sft.monitor import SftMonitor
class SftAgent(ActiveAgent):
    driver_type = SftDriver
    monitor_type = SftMonitor
