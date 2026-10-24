"""Reuse common active-agent wiring."""
from mosaic_uvm.components import ActiveAgent
from polynomial_unit.driver import PolynomialDriver
from polynomial_unit.monitor import PolynomialMonitor


class PolynomialAgent(ActiveAgent):
    driver_type = PolynomialDriver
    monitor_type = PolynomialMonitor
