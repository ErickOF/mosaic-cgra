"""Reuse shared sequencer, driver and monitor wiring."""

from mosaic_uvm.components import ActiveAgent
from accumulator.driver import AccumulatorDriver
from accumulator.monitor import AccumulatorMonitor


class AccumulatorAgent(ActiveAgent):
    driver_type = AccumulatorDriver
    monitor_type = AccumulatorMonitor
