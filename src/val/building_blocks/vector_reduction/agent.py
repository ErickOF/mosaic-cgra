"""Standard active-agent composition using the common sequencer wiring."""

from mosaic_uvm.components import ActiveAgent

from vector_reduction.driver import ReductionDriver
from vector_reduction.monitor import ReductionMonitor


class ReductionAgent(ActiveAgent):
    driver_type = ReductionDriver
    monitor_type = ReductionMonitor
