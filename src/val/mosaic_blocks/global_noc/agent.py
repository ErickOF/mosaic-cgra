"""Reuse shared UVM agent wiring."""
from mosaic_uvm.components import ActiveAgent
from global_noc.driver import NocDriver
from global_noc.monitor import NocMonitor
class NocAgent(ActiveAgent):
    driver_type=NocDriver
    monitor_type=NocMonitor
