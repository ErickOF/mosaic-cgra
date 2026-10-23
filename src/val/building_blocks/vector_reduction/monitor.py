"""Reuse established edge observation while exposing tree leaves and response DFFs."""

import cocotb
from mosaic_uvm.logic import logic
from vector_lane.monitor import LaneMonitor

from vector_reduction.transaction import INPUTS, OUTPUTS, Observation


class ReductionMonitor(LaneMonitor):
    def handles(self):
        core = cocotb.top.g_reduction
        handles = {}
        self.active["banks"] = {}
        for op in self.c.enabled_opcodes:
            operation = core.g_operation[op].g_enabled
            handles[f"active:{op}"] = operation.active
            leaves = operation.u_tree.g_level[0].g_leaves
            for k in range(self.c.count):
                handles[f"leaf:{op}:{k}"] = leaves.g_leaf[k].g_element.isolated
        for k in range(self.c.latency):
            stage = core.u_response.g_pipeline.g_stage[k]
            for kind, bank in (
                ("valid", stage.u_valid),
                ("metadata", stage.u_control),
                ("data", stage.g_data.u_data),
            ):
                resettable = kind != "data"
                name = ("control:" if resettable else "storage:") + f"{k}:{kind}"
                self.active["banks"][name] = resettable
                handles[name] = bank.o_q
                for pin in ("i_d", "i_enable", "i_rstb"):
                    handles[name + ":" + pin] = getattr(bank, pin)
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
