"""Standard shared active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from rdu.driver import RduDriver
from rdu.monitor import RduMonitor


class RduAgent(ActiveAgent):
    driver_type = RduDriver
    monitor_type = RduMonitor
