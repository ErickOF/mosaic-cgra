"""Retention agent components for specification-based PyUVM validation."""

from mosaic_uvm.components import ActiveAgent
from retention_register.driver import RetentionDriver
from retention_register.monitor import RetentionMonitor


class RetentionAgent(ActiveAgent):
    driver_type = RetentionDriver
    monitor_type = RetentionMonitor
