"""Mux agent components for specification-based PyUVM validation."""

from mosaic_uvm.components import ActiveAgent
from mux.driver import MuxDriver
from mux.monitor import MuxMonitor


class MuxAgent(ActiveAgent):
    driver_type = MuxDriver
    monitor_type = MuxMonitor
