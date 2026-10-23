"""Observe ports, isolated inputs and every reused DFF's real enable/reset pins."""

import cocotb
from cocotb.handle import HierarchyArrayObject, HierarchyObject
from mosaic_uvm.logic import logic
from multiplier.monitor import MultiplierMonitor

from vector_lane.transaction import INPUTS, OUTPUTS, Observation


class LaneMonitor(MultiplierMonitor):
    """Reuse the established edge, sample-window and between-edge watch machinery."""

    def handles(self):
        core = cocotb.top.g_lane
        handles = {
            name: getattr(core, name)
            for name in ("alu_request", "mul_request", "mac_request", "alu_a", "alu_b")
        }
        for family in ("mul", "mac"):
            if getattr(self.c, family):
                unit = getattr(core, "g_" + family)
                for operand in ("a", "b", "accumulator") if family == "mac" else ("a", "b"):
                    name = family + "_" + operand
                    handles[name] = getattr(unit, name)
        self.active["banks"] = {}

        def visit(scope):
            if (
                isinstance(scope, HierarchyObject)
                and hasattr(scope, "o_q")
                and all(hasattr(scope, name) for name in ("i_enable", "i_d", "i_rstb", "i_clk"))
            ):
                path = scope._path
                # Unreset data DFFs tie reset high. Control banks use the public reset.
                resettable = logic(scope.i_rstb) == "0"
                key = ("control:" if resettable else "storage:") + path
                self.active["banks"][key] = resettable
                handles[key] = scope.o_q
                for pin in ("i_enable", "i_d", "i_rstb"):
                    handles[key + ":" + pin] = getattr(scope, pin)
                return
            if isinstance(scope, (HierarchyObject, HierarchyArrayObject)):
                for child in scope:
                    if isinstance(child, (HierarchyObject, HierarchyArrayObject)):
                        visit(child)

        # The verification checker has its own history; walk only implementation scopes.
        for child in core:
            if child._name != "u_assertions" and isinstance(
                child, (HierarchyObject, HierarchyArrayObject)
            ):
                visit(child)
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
        # Watch DFF outputs only; enable/data/reset pins are combinational.
        if name in self.active["banks"]:
            await super().watch(name, handle)
