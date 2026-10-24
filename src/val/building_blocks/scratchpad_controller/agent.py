"""Sequencer, multi-client driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from scratchpad_controller.driver import ControllerDriver
from scratchpad_controller.monitor import ControllerMonitor


class ControllerAgent(ActiveAgent):
    driver_type = ControllerDriver
    monitor_type = ControllerMonitor
