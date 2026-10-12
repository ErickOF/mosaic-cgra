"""LaneMask agent components for specification-based PyUVM validation."""

from lane_mask.driver import LaneMaskDriver
from lane_mask.monitor import LaneMaskMonitor
from mosaic_uvm.components import ActiveAgent


class LaneMaskAgent(ActiveAgent):
    driver_type = LaneMaskDriver
    monitor_type = LaneMaskMonitor
