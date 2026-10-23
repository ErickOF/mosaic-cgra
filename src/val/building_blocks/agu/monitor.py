"""Observe ports before NBA, after settling, and throughout storage hold windows."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from mosaic_uvm.logic import logic
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor

from agu.transaction import INPUTS, OUTPUTS, STORAGE, Activity, Observation


class AguMonitor(uvm_monitor):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    def observe(self, stage):
        item = self.active["item"]
        obs = Observation(
            {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
            {name: logic(handle) for name, handle in self.active["internals"].items()},
            item,
            stage,
        )
        self.ap.write(obs)
        item.observation = obs
        if stage == "pre":
            item.pre = obs

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe("edge")

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            window = self.active["window"]
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                if window == "hold" or (
                    window == "inputs"
                    and name not in ("add_left", "add_right")
                    and not (
                        self.c.asynchronous
                        and logic(cocotb.top.i_rstb) == "0"
                        and (name in OUTPUTS or name in ("inner_index", "outer_index"))
                    )
                ):
                    self.ap.write(Activity(name, current))
                previous = current

    async def run_phase(self):
        await Timer(2, unit="ps")
        await ReadOnly()
        internals = self.active["internals"]
        if self.c.check_internals:
            bank = cocotb.top.g_sequence
            internals.update(
                {
                    name: getattr(bank, name)
                    for name in (*STORAGE, "add_left", "add_right")
                }
            )
            for label, instance in (
                ("descriptor", bank.u_descriptor_write),
                ("address", bank.u_address_write),
            ):
                for pin in (
                    "i_write_enable",
                    "i_suppress",
                    "o_write_enable",
                    "o_write_suppressed",
                ):
                    internals[f"gate:{label}:{pin}"] = getattr(instance, pin)
        tasks = [cocotb.start_soon(self.edges())]
        tasks.extend(
            cocotb.start_soon(self.watch(name, handle))
            for name, handle in (
                {
                    name: getattr(cocotb.top, name)
                    for name in OUTPUTS
                    if name != "o_config_ready"
                }
                | {
                    name: handle
                    for name, handle in internals.items()
                    if not name.startswith("gate:")
                }
            ).items()
        )
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                self.observe(self.active["stage"])
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
