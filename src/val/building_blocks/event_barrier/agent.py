"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from event_barrier.driver import EventBarrierDriver
from event_barrier.monitor import EventBarrierMonitor


class EventBarrierAgent(ActiveAgent):
    driver_type = EventBarrierDriver
    monitor_type = EventBarrierMonitor
