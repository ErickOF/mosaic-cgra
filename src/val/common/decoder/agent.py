"""Decoder agent components for specification-based PyUVM validation."""

from decoder.driver import DecoderDriver
from decoder.monitor import DecoderMonitor
from mosaic_uvm.components import ActiveAgent


class DecoderAgent(ActiveAgent):
    driver_type = DecoderDriver
    monitor_type = DecoderMonitor
