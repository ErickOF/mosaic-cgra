"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from sram_wrapper.driver import SramDriver
from sram_wrapper.monitor import SramMonitor


class SramAgent(ActiveAgent):
    driver_type = SramDriver
    monitor_type = SramMonitor
