"""Group driver, sequencer, and passive interface monitor."""
from mosaic_uvm.components import ActiveAgent
from lut_unit.driver import LutUnitDriver
from lut_unit.monitor import LutUnitMonitor


class LutUnitAgent(ActiveAgent):
    driver_type = LutUnitDriver
    monitor_type = LutUnitMonitor
