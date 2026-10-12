"""Dff agent components for specification-based PyUVM validation."""

from dff.driver import DffDriver
from dff.monitor import DffMonitor
from mosaic_uvm.components import ActiveAgent


class DffAgent(ActiveAgent):
    driver_type = DffDriver
    monitor_type = DffMonitor
