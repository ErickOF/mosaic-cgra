"""Generate a portable, immutable RTL bundle for a validated CGRA flavor."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flavor.model import ROOT, backend, dumps, parse, resolve


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identities(document):
    resolved, _ = resolve(document)
    architecture = hashlib.sha256(json.dumps(resolved, sort_keys=True).encode()).hexdigest()
    files = [ROOT / f"src/rtl/{name}.sv" for name in backend(resolved["cluster"]).SOURCES]
    files += list((ROOT / "src/gen/cluster").glob("*.py"))
    files += list(Path(__file__).parent.glob("*.py"))
    files += [ROOT / "src/gen/sft/sft_sources.py", ROOT / "src/gen/cpt/cpt_sources.py"]
    files += [ROOT / "src/gen/sft/contract.py", ROOT / "src/gen/cpt/cpt_contract.py",
              ROOT / "src/gen/tile_units.py"]
    fingerprints = {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}
    build = hashlib.sha256(json.dumps(dict(architecture=architecture,
        source_sha256=fingerprints), sort_keys=True).encode()).hexdigest()
    return resolved, architecture, build, fingerprints


def verify_bundle(bundle):
    """Check the complete export before reuse, simulation or download."""
    bundle = Path(bundle)
    record = json.loads((bundle / "generation.json").read_text())
    required = {"flavor.toml", "cluster.toml", "resolved.json", "manifest.json",
                "ports.json", "sources.f", "rtl/cluster.sv"}
    if (record.get("schema") != "mosaic-flavor-build-v1" or
            not required <= record.get("artifact_sha256", {}).keys()):
        raise ValueError("Incomplete flavor bundle")
    for name, expected in record["artifact_sha256"].items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle.resolve()) or digest(path) != expected:
            raise ValueError(f"Generated artifact changed: {name}")
    manifest = json.loads((bundle / "manifest.json").read_text())
    if (manifest["manifest_sha256"] != record["manifest_sha256"] or
            manifest["generated_rtl_sha256"] != digest(bundle / "rtl/cluster.sv")):
        raise ValueError("Bundle manifest does not match its generated RTL")
    return record


def generate(document, output_root=None):
    resolved, architecture, build, fingerprints = identities(document)
    output_root = Path(output_root or ROOT / "build/flavors").resolve()
    parent = output_root / resolved["name"]
    target = parent / build
    parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        record = verify_bundle(target)
        if record["build_id"] != build:
            raise ValueError("Cached generation identity does not match")
        return target, record
    with tempfile.TemporaryDirectory(prefix=".generating-", dir=parent) as directory:
        staging = Path(directory)
        source = staging / "flavor.toml"
        source.write_text(dumps(resolved))
        descriptor = staging / "cluster.toml"
        descriptor.write_text(dumps(resolved["cluster"]))
        engine = backend(resolved["cluster"])
        contract = engine.generate(descriptor, staging / "rtl/cluster.sv", staging)
        sources = []
        for name in engine.SOURCES:
            destination = staging / f"rtl/{name}.sv"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / f"src/rtl/{name}.sv", destination)
            sources.append(str(destination.relative_to(staging)))
        sources.append("rtl/cluster.sv")
        (staging / "sources.f").write_text("\n".join(sources) + "\n")
        (staging / "resolved.json").write_text(json.dumps(resolved, indent=2) + "\n")
        # Generation and copying must describe the same immutable source revision.
        if any(digest(ROOT / name) != expected for name, expected in fingerprints.items()):
            raise ValueError("Sources changed during generation; generate again")
        artifacts = {str(p.relative_to(staging)): digest(p) for p in sorted(staging.rglob("*"))
                     if p.is_file()}
        record = dict(schema="mosaic-flavor-build-v1", architecture_id=architecture,
            build_id=build, name=resolved["name"], top="cluster",
            manifest_sha256=contract["manifest_sha256"], source_sha256=fingerprints,
            artifact_sha256=artifacts, validation="NOT_RUN", synthesis="Design Compiler (deferred)")
        (staging / "generation.json").write_text(json.dumps(record, indent=2) + "\n")
        # Atomic publication prevents partially generated downloads.
        try:
            staging.rename(target)
        except FileExistsError:
            return target, verify_bundle(target)
    return target, record


def archive(bundle):
    bundle = Path(bundle)
    record = verify_bundle(bundle)
    destination = bundle.with_suffix(".zip")
    with tempfile.NamedTemporaryFile(dir=bundle.parent, suffix=".zip", delete=False) as file:
        temporary = Path(file.name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as output:
            for name in sorted([*record["artifact_sha256"], "generation.json"]):
                # Fixed metadata makes repeated exports byte-identical.
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                output.writestr(entry, (bundle / name).read_bytes())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flavor", required=True, type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    document = parse(args.flavor.read_text())
    if args.validate_only:
        resolve(document)
        print("Flavor is valid")
    else:
        target, record = generate(document, args.output_root)
        print(json.dumps(dict(bundle=str(target), build_id=record["build_id"],
                              archive=str(archive(target))), indent=2))


if __name__ == "__main__":
    main()
