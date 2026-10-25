"""Common active-agent composition with predicate-specific observations."""

from mosaic_uvm.components import ActiveAgent

from predicate_unit.driver import PredicateDriver
from predicate_unit.monitor import PredicateMonitor


class PredicateAgent(ActiveAgent):
    driver_type = PredicateDriver
    monitor_type = PredicateMonitor
