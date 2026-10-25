"""Standard sequencer, driver, and monitor composition."""
from mosaic_uvm.components import ActiveAgent
from banked_scratchpad.driver import ScratchpadDriver
from banked_scratchpad.monitor import ScratchpadMonitor


class ScratchpadAgent(ActiveAgent):
    driver_type = ScratchpadDriver
    monitor_type = ScratchpadMonitor
