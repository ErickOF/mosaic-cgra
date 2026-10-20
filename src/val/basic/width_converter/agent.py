"""Reuse shared sequencer, driver and monitor wiring."""

from mosaic_uvm.components import ActiveAgent
from width_converter.driver import WidthConverterDriver
from width_converter.monitor import WidthConverterMonitor


class WidthConverterAgent(ActiveAgent):
    driver_type = WidthConverterDriver
    monitor_type = WidthConverterMonitor
