"""Counter monitor components for specification-based PyUVM validation."""

from __future__ import annotations

import cocotb
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from counter.constants import CONTROLS
from counter.transaction import Inputs, Observation, State


class CounterMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    def inputs(self) -> Inputs:
        values = {}
        for name in CONTROLS:
            value = getattr(self.dut, f"i_{name}").value
            values[name] = int(value) if value.is_resolvable else str(value).lower()
        return Inputs(**values, load_value=int(self.dut.i_load_value.value))

    def state(self) -> State:
        return State(
            int(self.dut.o_count.value), int(self.dut.o_overflow.value),
            int(self.dut.o_underflow.value),
        )

    async def run_phase(self):
        while True:
            await FallingEdge(self.dut.i_clk)
            await Timer(self.config.clock_ns / 4, unit="ns")
            await ReadOnly()
            item = self.active["item"]
            if item is None:
                continue
            mid_inputs = self.inputs()
            mid_state = self.state()
            mid_terminal = int(self.dut.o_terminal.value)
            await RisingEdge(self.dut.i_clk)
            edge_inputs = self.inputs()
            await Timer(self.config.sample_ns, unit="ns")
            await ReadOnly()
            self.ap.write(Observation(
                item.get_name(), mid_inputs, edge_inputs, mid_state, self.state(),
                mid_terminal, int(self.dut.o_terminal.value), item.unknown,
                item.pulse_reset,
            ))
