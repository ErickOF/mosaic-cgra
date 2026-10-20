"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from register_file.driver import RegisterFileDriver
from register_file.monitor import RegisterFileMonitor


class RegisterFileAgent(ActiveAgent):
    driver_type = RegisterFileDriver
    monitor_type = RegisterFileMonitor
