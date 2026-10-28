"""Active runtime ready-valid agent."""
from mosaic_uvm.components import ActiveAgent
from runtime_controller.driver import RuntimeDriver
from runtime_controller.monitor import RuntimeMonitor


class RuntimeAgent(ActiveAgent):
    driver_type = RuntimeDriver
    monitor_type = RuntimeMonitor
