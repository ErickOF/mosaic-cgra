"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from store_engine.driver import StoreEngineDriver
from store_engine.monitor import StoreEngineMonitor


class StoreEngineAgent(ActiveAgent):
    driver_type = StoreEngineDriver
    monitor_type = StoreEngineMonitor
