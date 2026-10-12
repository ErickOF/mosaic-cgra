"""ResetSynchronizer agent components for specification-based PyUVM validation."""

from mosaic_uvm.components import ActiveAgent
from reset_synchronizer.driver import ResetSynchronizerDriver
from reset_synchronizer.monitor import ResetSynchronizerMonitor


class ResetSynchronizerAgent(ActiveAgent):
    driver_type = ResetSynchronizerDriver
    monitor_type = ResetSynchronizerMonitor
