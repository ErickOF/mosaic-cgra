"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from vector_register_file.driver import VectorRegisterFileDriver
from vector_register_file.monitor import VectorRegisterFileMonitor


class VectorRegisterFileAgent(ActiveAgent):
    driver_type = VectorRegisterFileDriver
    monitor_type = VectorRegisterFileMonitor
