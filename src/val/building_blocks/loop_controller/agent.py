"""Group driver, sequencer, and passive interface monitor."""
from mosaic_uvm.components import ActiveAgent
from loop_controller.driver import LoopControllerDriver
from loop_controller.monitor import LoopControllerMonitor


class LoopControllerAgent(ActiveAgent):
    driver_type = LoopControllerDriver
    monitor_type = LoopControllerMonitor
