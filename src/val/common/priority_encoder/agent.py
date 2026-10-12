"""PriorityEncoder agent components for specification-based PyUVM validation."""

from mosaic_uvm.components import ActiveAgent
from priority_encoder.driver import PriorityEncoderDriver
from priority_encoder.monitor import PriorityEncoderMonitor


class PriorityEncoderAgent(ActiveAgent):
    driver_type = PriorityEncoderDriver
    monitor_type = PriorityEncoderMonitor
