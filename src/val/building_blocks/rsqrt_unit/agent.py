"""Reuse common active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from rsqrt_unit.driver import RsqrtDriver
from rsqrt_unit.monitor import RsqrtMonitor


class RsqrtAgent(ActiveAgent):
    driver_type = RsqrtDriver
    monitor_type = RsqrtMonitor
