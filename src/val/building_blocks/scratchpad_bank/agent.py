"""Group the sequencer, driver, and passive monitor."""
from mosaic_uvm.components import ActiveAgent
from scratchpad_bank.driver import ScratchpadBankDriver
from scratchpad_bank.monitor import ScratchpadBankMonitor


class ScratchpadBankAgent(ActiveAgent):
    driver_type = ScratchpadBankDriver
    monitor_type = ScratchpadBankMonitor
