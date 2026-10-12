"""WriteGate agent components for specification-based PyUVM validation."""

from mosaic_uvm.components import ActiveAgent
from write_gate.driver import WriteGateDriver
from write_gate.monitor import WriteGateMonitor


class WriteGateAgent(ActiveAgent):
    driver_type = WriteGateDriver
    monitor_type = WriteGateMonitor
