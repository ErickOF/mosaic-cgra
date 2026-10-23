"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from stream_formatter.driver import StreamFormatterDriver
from stream_formatter.monitor import StreamFormatterMonitor


class StreamFormatterAgent(ActiveAgent):
    driver_type = StreamFormatterDriver
    monitor_type = StreamFormatterMonitor
