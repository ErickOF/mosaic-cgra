"""Standard shared active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from performance_counters.driver import PerformanceCountersDriver
from performance_counters.monitor import PerformanceCountersMonitor


class PerformanceCountersAgent(ActiveAgent):
    driver_type = PerformanceCountersDriver
    monitor_type = PerformanceCountersMonitor
