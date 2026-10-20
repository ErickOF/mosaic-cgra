"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from skid_buffer.driver import SkidBufferDriver
from skid_buffer.monitor import SkidBufferMonitor


class SkidBufferAgent(ActiveAgent):
    driver_type = SkidBufferDriver
    monitor_type = SkidBufferMonitor
