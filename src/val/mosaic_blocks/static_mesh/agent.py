"""Shared UVM agent wiring."""

from mosaic_uvm.components import ActiveAgent
from static_mesh.driver import MeshDriver
from static_mesh.monitor import MeshMonitor


class MeshAgent(ActiveAgent):
    driver_type = MeshDriver
    monitor_type = MeshMonitor
