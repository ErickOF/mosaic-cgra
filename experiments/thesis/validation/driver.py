"""Public interfaces, delayed supply peers and stable-transfer monitoring."""

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
driver_spec = importlib.util.spec_from_file_location("thesis_fabric_driver",
    ROOT / "src/val/mosaic_blocks/flavor/driver.py")
driver_module = importlib.util.module_from_spec(driver_spec)
driver_spec.loader.exec_module(driver_module)
FabricDriver = driver_module.FabricDriver


class ExperimentDriver(FabricDriver):
    """Public-port sampler with delayed supply peers and lossless handshake trace."""

    def build_phase(self):
        super().build_phase()
        self.trace = []
        self.phase = "reset"
        self.sample_ports = []
        self.last = {}
        self.pending_outputs = {}
        self.peer_history = {}
        self.tiles = []
        self.interface = {}

    async def cycle(self, values=None, sample=()):
        peers = {}
        peers["i_thesis_memory_stall"] = int(getattr(self, "backpressure", False)
            and self.phase == "kernel" and self.cycles % 11 < 5)
        for tile in self.tiles:
            ident = tile["id"]
            for out, inp in (("body_power_enable", "body_power_good"),
                             ("body_isolate", "body_isolation_ack")):
                request, ack = f"o_tile_{ident}_{out}", f"i_tile_{ident}_{inp}"
                history = self.peer_history.setdefault(request, [0, 0, 0])
                raw = getattr(self.dut, request).value
                history.append(int(raw) if raw.is_resolvable else 0)
                peers[ack] = history.pop(0)
            for out, inp in (("body_save", "body_save_done"),
                             ("body_restore", "body_restore_done")):
                value = getattr(self.dut, f"o_tile_{ident}_{out}").value
                peers[f"i_tile_{ident}_{inp}"] = int(value) if value.is_resolvable else 0
        names = list(dict.fromkeys([*sample, *self.sample_ports]))
        observed = await super().cycle(peers | (values or {}), names)
        if os.getenv("THESIS_DEBUG") and self.cycles % 1000 == 0:
            print(f"Thesis: {self.phase}, cycle {self.cycles}", flush=True)
        self.last = observed
        if peers["i_thesis_memory_stall"]:
            self.trace.append(dict(kind="memory_hold", phase=self.phase, cycle=self.cycles))
        if int(self.dut.i_rstb.value):
            for tile in self.tiles:
                ident, width = tile["id"], tile["native_data_width"]
                meta = tile["native_metadata_width"]
                prefix = f"o_thesis_tile_{ident}_"
                for group, valid, ready in (("input", "data_in_valid", "data_in_ready"),
                                            ("output", "data_out_valid", "data_out_ready")):
                    for port in range(tile["inputs"] if group == "input" else tile["outputs"]):
                        key = ident, group, port
                        offered = observed[prefix + valid] >> port & 1
                        accepted = offered and observed[prefix + ready] >> port & 1
                        word = (observed[prefix + f"data_{'in' if group == 'input' else 'out'}_payload"]
                                >> (port * width)) & ((1 << width) - 1)
                        metadata = (observed[prefix +
                            f"data_{'in' if group == 'input' else 'out'}_metadata"] >> (port * meta)
                            & ((1 << meta) - 1))
                        if key in self.pending_outputs:
                            assert offered and (word, metadata) == self.pending_outputs[key], (
                                "Pending packet changed", key, self.phase, self.cycles)
                        if offered and not accepted:
                            self.pending_outputs[key] = word, metadata
                        else:
                            self.pending_outputs.pop(key, None)
                        if accepted:
                            self.trace.append(dict(cycle=self.cycles, phase=self.phase,
                                kind="transfer", tile=ident, direction=group, port=port,
                                data=word, metadata=metadata))
                for suffix in ("status_error", "status_fatal_error"):
                    assert not observed[f"o_tile_{ident}_{suffix}"], (
                        "Native tile error", ident, self.phase, self.cycles,
                        observed.get(f"o_tile_{ident}_status_error_code"))
                if observed[f"o_tile_{ident}_status_power_state"] == 4:
                    assert not (observed[prefix + "data_in_valid"] &
                                observed[prefix + "data_in_ready"]), ("OFF accepted work", ident)
                if tile["module"] == "mst":
                    for kind in ("read", "write"):
                        base = prefix + f"scratchpad_{kind}_"
                        if observed[base + "valid"] and observed[base + "ready"]:
                            address = observed[base + "address"]
                            self.trace.append(dict(kind="memory", direction=kind,
                                phase=self.phase, cycle=self.cycles, tile=ident, address=address,
                                bytes=1 << observed[base + "size_log2"],
                                bank=(address // 8) % 8))
                        elif observed[base + "valid"]:
                            self.trace.append(dict(kind="memory_wait", direction=kind,
                                phase=self.phase, cycle=self.cycles, tile=ident))
                state = tuple(observed[f"o_tile_{ident}_{n}"] for n in (
                    "status_power_state", "body_power_enable", "body_isolate"))
                previous = self.peer_history.get((ident, "state"))
                if previous != state:
                    self.trace.append(dict(cycle=self.cycles, phase=self.phase, kind="power",
                        tile=ident, previous=previous, state=state,
                        power_good=peers[f"i_tile_{ident}_body_power_good"],
                        isolation_ack=peers[f"i_tile_{ident}_body_isolation_ack"],
                        pending_packets=len(self.pending_outputs)))
                    self.peer_history[(ident, "state")] = state
            if observed.get("o_memory_bank_conflict", 0):
                self.trace.append(dict(kind="bank_conflict", phase=self.phase,
                    cycle=self.cycles, mask=observed["o_memory_bank_conflict"]))
        return observed


