"""Reusable UVM agent composition."""

from mosaic_uvm.components import ActiveAgent
from tile_network_interface.driver import InterfaceDriver
from tile_network_interface.monitor import InterfaceMonitor


class InterfaceAgent(ActiveAgent):
    driver_type = InterfaceDriver
    monitor_type = InterfaceMonitor
