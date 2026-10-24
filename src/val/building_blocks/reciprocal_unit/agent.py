"""Reuse common active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from reciprocal_unit.driver import ReciprocalDriver
from reciprocal_unit.monitor import ReciprocalMonitor


class ReciprocalAgent(ActiveAgent):
    driver_type = ReciprocalDriver
    monitor_type = ReciprocalMonitor
