"""IsolationCell agent components for specification-based PyUVM validation."""

from isolation_cell.driver import IsolationCellDriver
from isolation_cell.monitor import IsolationCellMonitor
from mosaic_uvm.components import ActiveAgent


class IsolationCellAgent(ActiveAgent):
    driver_type = IsolationCellDriver
    monitor_type = IsolationCellMonitor
