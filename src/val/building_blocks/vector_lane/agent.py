"""Standard active-agent composition using the common sequencer wiring."""

from mosaic_uvm.components import ActiveAgent

from vector_lane.driver import LaneDriver
from vector_lane.monitor import LaneMonitor


class LaneAgent(ActiveAgent):
    driver_type = LaneDriver
    monitor_type = LaneMonitor
