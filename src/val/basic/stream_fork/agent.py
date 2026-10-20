"""Reuse common active-agent wiring."""

from mosaic_uvm.components import ActiveAgent
from stream_fork.driver import StreamForkDriver
from stream_fork.monitor import StreamForkMonitor


class StreamForkAgent(ActiveAgent):
    driver_type = StreamForkDriver
    monitor_type = StreamForkMonitor
