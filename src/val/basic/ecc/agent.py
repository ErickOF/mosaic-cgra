"""Active PyUVM codec agent using the shared sequencer wiring."""

from mosaic_uvm.components import ActiveAgent
from ecc.driver import EccDriver
from ecc.monitor import EccMonitor


class EccAgent(ActiveAgent):
    driver_type=EccDriver
    monitor_type=EccMonitor
