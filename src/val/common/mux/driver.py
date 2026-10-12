"""Mux driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits
from mux.model import interval_kind


class MuxDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            packed = item.inputs.packed_data(self.config)
            select = bits(item.inputs.select, self.config.select_width)
            kind = interval_kind(self.config, str(cocotb.top.i_data.value).lower(),
                                 str(cocotb.top.i_select.value).lower(), packed, select)
            self.active.update(item=item, stage="settled", kind=kind,
                               quiet=kind in ("stable", "unselected", "invalid"))
            cocotb.top.i_data.value = packed
            cocotb.top.i_select.value = select
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            # Once settled, all inputs remain stable until the next transaction.
            self.active["quiet"] = True
            await Timer(item.hold_ns, unit="ns")
            assert not self.active["sample"].is_set(), "Monitor missed the settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()
