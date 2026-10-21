"""Reuse the common active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from agu.driver import AguDriver
from agu.monitor import AguMonitor


class AguAgent(ActiveAgent):
    driver_type = AguDriver
    monitor_type = AguMonitor
