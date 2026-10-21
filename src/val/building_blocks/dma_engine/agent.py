"""Reuse the shared active UVM agent construction."""
from mosaic_uvm.components import ActiveAgent
from dma_engine.driver import DmaDriver
from dma_engine.monitor import DmaMonitor


class DmaAgent(ActiveAgent):
    driver_type=DmaDriver
    monitor_type=DmaMonitor
