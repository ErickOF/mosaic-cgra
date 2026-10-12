"""OperandIsolation driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits


class OperandIsolationDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            data, control = bits(item.inputs.data, self.config.width), bits(item.inputs.isolate, 1)
            old_control = str(cocotb.top.i_isolate.value).lower()
            old_data = str(cocotb.top.i_data.value).lower()
            self.active.update(item=item, stage="settled", quiet=(
                old_control == control and (control != "0" or old_data == data)
            ))
            cocotb.top.i_data.value = data
            cocotb.top.i_isolate.value = control
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            self.active["quiet"] = True
            await Timer(item.hold_ns, unit="ns")
            assert not self.active["sample"].is_set(), "Monitor missed the settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()
