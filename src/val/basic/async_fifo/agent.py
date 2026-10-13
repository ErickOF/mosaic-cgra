"""Active dual-clock stimulus and observation agent."""

from mosaic_uvm.components import ActiveAgent
from async_fifo.driver import AsyncFifoDriver
from async_fifo.monitor import AsyncFifoMonitor


class AsyncFifoAgent(ActiveAgent):
    driver_type = AsyncFifoDriver
    monitor_type = AsyncFifoMonitor
