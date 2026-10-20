"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from register_slice.driver import RegisterSliceDriver
from register_slice.monitor import RegisterSliceMonitor


class RegisterSliceAgent(ActiveAgent):
    driver_type = RegisterSliceDriver
    monitor_type = RegisterSliceMonitor
