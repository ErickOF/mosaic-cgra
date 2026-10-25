"""Run the decorated PyUVM test and check the actual vector_lane elaboration."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test

from vector_lane.config import LaneConfig
from vector_lane.env import LaneEnv
from vector_lane.sequences import LaneSequence
from vector_lane.transaction import INPUTS


@test(timeout_time=1, timeout_unit="ms")
class LaneTest(uvm_test):
    def build_phase(self):
        c = self.config = LaneConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f"Wrong port width: {name}"
        if c.check_internals:
            for name, value in c.parameters.items():
                handle = getattr(cocotb.top, name)
                observed = int(handle.value)
                # Some VPI backends expose signed parameters as raw packed bits.
                if value < 0 and observed >= 0:
                    observed -= 1 << len(handle)
                assert observed == value, f"Wrong parameter: {name}"
            assert int(cocotb.top.PRODUCT_WIDTH.value) == 2 * c.element
            assert hasattr(cocotb.top.g_lane, "g_mul") == bool(c.mul)
            assert hasattr(cocotb.top.g_lane, "g_mac") == bool(c.mac)
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_lane, "u_assertions"), "HDL checker missing"
        ConfigDB().set(self, "env.*", "config", c)
        ConfigDB().set(
            self,
            "env.*",
            "active",
            {"item": None, "window": "initial", "sample": Event(), "internals": {}},
        )
        self.env = LaneEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await LaneSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
