"""ClockGate driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from clock_gate.constants import CONTROLS


class ClockGateDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        # Give the passive monitor time to observe the defined startup low phase.
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active["item"] = item
            events = [(self.config.half_ps, "clock", 1), (self.config.period_ps, "clock", 0)]
            events.extend((change.offset_ps, "controls", change) for change in item.changes)
            previous = 0
            for offset, kind, value in sorted(events, key=lambda event: event[0]):
                assert previous < offset <= self.config.period_ps, (
                    "Stimulus must not coincide with a source-clock edge"
                )
                await Timer(offset - previous, unit="ps")
                previous = offset
                if kind == "clock":
                    self.dut.i_clk.value = value
                else:
                    for name in CONTROLS:
                        control = getattr(value, name)
                        if control is not None:
                            getattr(self.dut, f"i_{name}").value = control
            await ReadOnly()
            self.seq_item_port.item_done()
