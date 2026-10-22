"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from local_switch.driver import LocalSwitchDriver
from local_switch.monitor import LocalSwitchMonitor


class LocalSwitchAgent(ActiveAgent):
    driver_type = LocalSwitchDriver
    monitor_type = LocalSwitchMonitor
