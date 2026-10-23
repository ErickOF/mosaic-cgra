"""Reuse the common UVM active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from noc_router.driver import RouterDriver
from noc_router.monitor import RouterMonitor


class RouterAgent(ActiveAgent):
    driver_type = RouterDriver
    monitor_type = RouterMonitor
