"""Packer sequencer, driver and monitor wiring."""

from mosaic_uvm.components import ActiveAgent
from packer.driver import PackerDriver
from packer.monitor import PackerMonitor


class PackerAgent(ActiveAgent):
    driver_type = PackerDriver
    monitor_type = PackerMonitor
