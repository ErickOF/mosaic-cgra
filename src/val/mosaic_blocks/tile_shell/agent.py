"""Reusable active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from tile_shell.driver import TileShellDriver
from tile_shell.monitor import TileShellMonitor
class TileShellAgent(ActiveAgent):
    driver_type = TileShellDriver
    monitor_type = TileShellMonitor
