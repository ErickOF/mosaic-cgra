"""Reuse standard active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from round_robin_arbiter.driver import ArbiterDriver
from round_robin_arbiter.monitor import ArbiterMonitor


class ArbiterAgent(ActiveAgent):
    driver_type = ArbiterDriver
    monitor_type = ArbiterMonitor
