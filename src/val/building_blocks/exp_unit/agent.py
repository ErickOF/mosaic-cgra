"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from exp_unit.driver import ExpUnitDriver
from exp_unit.monitor import ExpUnitMonitor


class ExpUnitAgent(ActiveAgent):
    driver_type = ExpUnitDriver
    monitor_type = ExpUnitMonitor
