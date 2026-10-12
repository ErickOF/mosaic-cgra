"""Counter agent components for specification-based PyUVM validation."""

from counter.driver import CounterDriver
from counter.monitor import CounterMonitor
from mosaic_uvm.components import ActiveAgent


class CounterAgent(ActiveAgent):
    driver_type = CounterDriver
    monitor_type = CounterMonitor
