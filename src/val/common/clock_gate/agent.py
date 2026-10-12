"""ClockGate agent components for specification-based PyUVM validation."""

from clock_gate.driver import ClockGateDriver
from clock_gate.monitor import ClockGateMonitor
from mosaic_uvm.components import ActiveAgent


class ClockGateAgent(ActiveAgent):
    driver_type = ClockGateDriver
    monitor_type = ClockGateMonitor
