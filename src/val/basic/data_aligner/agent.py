"""Active PyUVM agent for the byte-window interface."""

from mosaic_uvm.components import ActiveAgent
from data_aligner.driver import AlignerDriver
from data_aligner.monitor import AlignerMonitor


class AlignerAgent(ActiveAgent):
    driver_type = AlignerDriver
    monitor_type = AlignerMonitor
