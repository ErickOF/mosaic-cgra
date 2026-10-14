"""FIFO sequencer, driver and monitor wiring."""

from mosaic_uvm.components import ActiveAgent
from fifo.driver import FifoDriver
from fifo.monitor import FifoMonitor


class FifoAgent(ActiveAgent):
    driver_type = FifoDriver
    monitor_type = FifoMonitor
