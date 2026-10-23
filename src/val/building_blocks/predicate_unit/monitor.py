"""Observe the real per-lane state DFFs, response DFF and isolated read operands."""

import cocotb
from mosaic_uvm.logic import logic
from multiplier.monitor import MultiplierMonitor

from predicate_unit.transaction import INPUTS, OUTPUTS, Observation


class PredicateMonitor(MultiplierMonitor):
    def handles(self):
        core = cocotb.top.g_predicate
        handles = {}
        self.active["banks"] = {}
        banks = [("response", core.u_response, True)]
        for entry in range(self.c.depth):
            for lane in range(self.c.lanes):
                scope = core.g_entry[entry].g_lane[lane]
                banks.extend(
                    (
                        (f"data:{entry}:{lane}", scope.u_data, False),
                        (f"valid:{entry}:{lane}", scope.u_valid, True),
                    )
                )
        for label, bank, resettable in banks:
            key = ("control:" if resettable else "storage:") + label
            self.active["banks"][key] = resettable
            handles[key] = bank.o_q
            for pin in ("i_enable", "i_d", "i_rstb"):
                handles[key + ":" + pin] = getattr(bank, pin)
        for port in range(2):
            scope = core.g_read[port]
            handles[f"decode:{port}"] = scope.decoded
            handles[f"read:{port}"] = scope.selected_data
            handles[f"read_valid:{port}"] = scope.selected_valid
        handles["destination"] = core.destination_decoded
        handles["external"] = core.external_data
        return handles

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

    async def watch(self, name, handle):
        # Enables/data/reset pins are combinational; only Q must obey clocking.
        if name in self.active["banks"]:
            await super().watch(name, handle)
