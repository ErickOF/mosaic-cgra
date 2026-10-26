"""Standard UVM agent with shared clock/fault driving."""

from mosaic_uvm.components import ActiveAgent
from predicate_network.driver import PredicateDriver
from predicate_network.monitor import PredicateMonitor


class PredicateAgent(ActiveAgent):
    driver_type = PredicateDriver
    monitor_type = PredicateMonitor
