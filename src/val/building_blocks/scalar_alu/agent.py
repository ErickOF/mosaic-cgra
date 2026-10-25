"""Reuse the common PyUVM active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from scalar_alu.driver import AluDriver
from scalar_alu.monitor import AluMonitor


class AluAgent(ActiveAgent):
    driver_type = AluDriver
    monitor_type = AluMonitor
