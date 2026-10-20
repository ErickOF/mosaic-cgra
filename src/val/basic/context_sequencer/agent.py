"""Sequencer agent using the common PyUVM sequencer/driver/monitor wiring."""

from mosaic_uvm.components import ActiveAgent
from context_sequencer.driver import SequencerDriver
from context_sequencer.monitor import SequencerMonitor


class SequencerAgent(ActiveAgent):
    driver_type = SequencerDriver
    monitor_type = SequencerMonitor
