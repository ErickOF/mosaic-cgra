"""LevelShifter agent components for specification-based PyUVM validation."""

from level_shifter.driver import LevelShifterDriver
from level_shifter.monitor import LevelShifterMonitor
from mosaic_uvm.components import ActiveAgent


class LevelShifterAgent(ActiveAgent):
    driver_type = LevelShifterDriver
    monitor_type = LevelShifterMonitor
