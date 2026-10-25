"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from load_engine.driver import LoadEngineDriver
from load_engine.monitor import LoadEngineMonitor


class LoadEngineAgent(ActiveAgent):
    driver_type = LoadEngineDriver
    monitor_type = LoadEngineMonitor
