"""LaneMask monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from lane_mask.constants import OUTPUTS, SOURCES
from lane_mask.transaction import Observation


class LaneMaskMonitor(uvm_monitor):
    """Read actual interface ports, including repeated unchanged transactions."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        while True:
            await self.active["sample"].wait()
            await ReadOnly()
            item = self.active["item"]
            self.ap.write(Observation(
                item.get_name(),
                tuple(str(getattr(cocotb.top, name).value).lower() for name in ("i_operation_valid", *SOURCES)),
                tuple(str(getattr(cocotb.top, name).value).lower() for name in OUTPUTS),
                item.inputs, item.expected_unknown,
            ))
            self.active["sample"].clear()
