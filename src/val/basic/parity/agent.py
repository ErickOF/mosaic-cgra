"""Generation/checking sequencer, driver and monitor wiring."""

from mosaic_uvm.components import ActiveAgent
from parity.driver import ParityDriver
from parity.monitor import ParityMonitor


class ParityAgent(ActiveAgent):
    driver_type = ParityDriver
    monitor_type = ParityMonitor
