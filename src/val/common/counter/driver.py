"""Counter driver components for specification-based PyUVM validation."""

from dataclasses import asdict
import cocotb
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_driver


class CounterDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        # The test starts with reset asserted. Complete one initialization
        # edge before observing a synchronous counter's otherwise unknown state.
        await RisingEdge(self.dut.i_clk)
        while True:
            item = await self.seq_item_port.get_next_item()
            await FallingEdge(self.dut.i_clk)
            self.active["item"] = item
            for name, value in asdict(item.inputs).items():
                getattr(self.dut, f"i_{name}").value = value
            if item.pulse_reset:
                # Assert while the clock is low and release before its next
                # rising edge. Only an asynchronous counter may reset here.
                await Timer(self.config.clock_ns * 3 / 8, unit="ns")
                self.dut.i_rstb.value = 1
            await RisingEdge(self.dut.i_clk)
            await Timer(self.config.sample_ns, unit="ns")
            await ReadOnly()
            # Allow the passive monitor and scoreboard to complete before
            # finish_item can let the test drop its final objection.
            await Timer(1, unit="ps")
            self.active["item"] = None
            self.seq_item_port.item_done()
