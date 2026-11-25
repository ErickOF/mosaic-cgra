"""Opt-in experimental integration of the existing Configurable RTL generator.

Only metadata is adapted. The test supplies a receiver's native metadata record
for each packet, based on its validated context or store descriptor. The data
path, SRAM, native engines, ready/valid protocol and width checks remain real.
These adapters and observability ports are part of the exported RTL/netlist and
its identity; they must also be included in any later energy comparison.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from cases import ROOT, digest
from schedule import domains
from flavor import fabric
from flavor.generate import digest as file_digest, generate as base_generate, verify_bundle
from flavor.model import generator, resolve


class ExperimentFabric(fabric.Fabric):
    def instance(self, module, prefix, aliases, parameters=None, bindings=None, expose=None):
        if module == "mosaic_blocks/cluster_memory_bridge":
            bindings = dict(bindings)
            valid_target, ready_source = bindings["o_request_valid"], bindings["i_request_ready"]
            raw = self.wire(prefix + "_memory_request_valid")
            ready = self.wire(prefix + "_memory_request_ready")
            stall = self.port("i_thesis_memory_stall", "input")
            bindings.update(o_request_valid=raw, i_request_ready=ready)
            super().assign(valid_target, f"{raw} && !{stall}")
            super().assign(ready, f"{ready_source} && !{stall}")
        mapping = super().instance(module, prefix, aliases, parameters, bindings, expose)
        if module == "building_blocks/local_switch":
            width = aliases["METADATA_WIDTH"]
            raw = mapping["o_output_metadata"]
            adapted = self.wire(raw + "_adapted", 6 * width)
            for port in range(6):
                value = f"{raw}[{port * width}+:{width}]"
                if port < 2:
                    tile_id = prefix.removeprefix("router_")
                    control = self.port(f"i_thesis_{tile_id}_metadata_{port}", "input", width)
                    enable = self.port(f"i_thesis_{tile_id}_adapt_{port}", "input")
                    value = f"{enable} ? {control} : {value}"
                super().assign(f"{adapted}[{port * width}+:{width}]", value)
            mapping["o_output_metadata"] = adapted
        elif module.startswith("mosaic_blocks/") and prefix.startswith("tile_"):
            self.port(f"i_thesis_{prefix}_stall", "input")
            for name in ("i_data_in_valid", "o_data_in_ready", "i_data_in_payload",
                         "i_data_in_metadata", "o_data_out_valid", "i_data_out_ready",
                         "o_data_out_payload", "o_data_out_metadata"):
                signal = self.port(f"o_thesis_{prefix}_{name[2:]}", "output",
                                   self.port_catalog(module, aliases)[name][1])
                super().assign(signal, mapping[name])
            if module == "mosaic_blocks/mst":
                for kind in ("read", "write"):
                    for name in (f"o_scratchpad_{kind}_valid", f"i_scratchpad_{kind}_ready",
                                 f"o_scratchpad_{kind}_address", f"o_scratchpad_{kind}_size_log2"):
                        signal = self.port(f"o_thesis_{prefix}_{name[2:]}", "output",
                                           self.port_catalog(module, aliases)[name][1])
                        super().assign(signal, mapping[name])
        return mapping

    def assign(self, left, right):
        # A deterministic link stall is applied on both sides of the handshake.
        # Pending data and metadata are still generated and held by native RTL.
        match = re.fullmatch(r"router_(\d+)_i_input_valid\[([01])\]", left)
        match_ready = re.fullmatch(r"tile_(\d+)_i_data_out_ready(?:\[([01])\])?", left)
        if match or match_ready:
            tile = (match or match_ready)[1]
            right = f"({right}) && !i_thesis_tile_{tile}_stall"
        super().assign(left, right)


def generate(document, output, *, power=False):
    """Extend a verified immutable export; ordinary app exports are untouched."""
    source, base = base_generate(document, Path(output) / "base")
    resolved, geometry = resolve(document)
    # These native options are qualified only by this opt-in power-model suite.
    # They remain unavailable in the normal editor/catalog.
    for native in geometry["native"]:
        if native["tile"]["class"] == "VCT":
            # Released full graph permits an external accumulator operand (y).
            native["parameters"]["BYPASS_PROFILE"] = 2
        if power and native["tile"]["class"] in ("BCT", "VCT"):
            native["parameters"]["SUPPORT_POWER_OFF"] = 1
    files = sorted(Path(__file__).parent.glob("*.py"))
    fingerprints = {str(p.relative_to(ROOT)): file_digest(p) for p in files}
    identity = digest(dict(base_build=base["build_id"], power_model=power,
                           experiment_sources=fingerprints))
    target = Path(output) / resolved["name"] / identity
    if target.exists():
        return target, verify_bundle(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    destination = target
    staging = Path(tempfile.mkdtemp(prefix=".experiment-", dir=target.parent))
    target = staging / "bundle"
    shutil.copytree(source, target)
    try:
        wrapper, tiles, boundaries = fabric.build(resolved["cluster"], geometry,
                                                 wrapper=ExperimentFabric())
        manifest = json.loads((target / "manifest.json").read_text())
        manifest.pop("manifest_sha256")
        manifest.pop("generated_rtl_sha256")
        manifest.update(tile_parameter_table=tiles, boundaries=boundaries,
            experiment=dict(schema="mosaic-thesis-adapter-v1", power_model=power,
                metadata="explicit per-packet native receiver metadata; data remains unmodified",
                stalls="native output valid/ready are gated together",
                domains=domains(resolved["cluster"])))
        manifest["manifest_sha256"] = digest(manifest)
        rtl = target / "rtl/cluster.sv"
        rtl.write_text(generator.format_rtl(wrapper.render(manifest["manifest_sha256"])))
        manifest["generated_rtl_sha256"] = file_digest(rtl)
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (target / "ports.json").write_text(json.dumps(wrapper.public, indent=2) + "\n")
        (target / "domains.json").write_text(json.dumps(domains(resolved["cluster"]), indent=2)
                                            + "\n")
        record = base | dict(build_id=identity, parent_build_id=base["build_id"],
            source_sha256=base["source_sha256"] | fingerprints,
            manifest_sha256=manifest["manifest_sha256"],
            artifact_sha256={str(p.relative_to(target)): file_digest(p)
                for p in sorted(target.rglob("*")) if p.is_file() and p.name != "generation.json"})
        (target / "generation.json").write_text(json.dumps(record, indent=2) + "\n")
        verify_bundle(target)
        try:
            target.rename(destination)
        except FileExistsError:
            return destination, verify_bundle(destination)
        return destination, record
    except BaseException:
        shutil.rmtree(target)
        raise
    finally:
        shutil.rmtree(staging)
