"""OperandIsolation agent components for specification-based PyUVM validation."""

from mosaic_uvm.components import ActiveAgent
from operand_isolation.driver import OperandIsolationDriver
from operand_isolation.monitor import OperandIsolationMonitor


class OperandIsolationAgent(ActiveAgent):
    driver_type = OperandIsolationDriver
    monitor_type = OperandIsolationMonitor
