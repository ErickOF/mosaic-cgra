"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from stream_join.driver import StreamJoinDriver
from stream_join.monitor import StreamJoinMonitor


class StreamJoinAgent(ActiveAgent):
    driver_type = StreamJoinDriver
    monitor_type = StreamJoinMonitor
