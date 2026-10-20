"""Active configuration agent and driver-coordinated read/state monitor."""

from mosaic_uvm.components import ActiveAgent
from context_memory.driver import ContextMemoryDriver
from context_memory.monitor import ContextMemoryMonitor


class ContextMemoryAgent(ActiveAgent):
    driver_type = ContextMemoryDriver
    monitor_type = ContextMemoryMonitor
