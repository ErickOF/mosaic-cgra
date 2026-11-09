"""Architecture documents shared by the visual editor, CLI and generator."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
CLUSTER = ROOT / "src/gen/cluster"
sys.path.insert(0, str(CLUSTER))
spec = importlib.util.spec_from_file_location("flavor_cluster_generator", CLUSTER / "generate.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
from tile_parameters import tile_parameters
from flavor import fabric
from flavor.guidance import ARCHITECTURE, SCOPE, TILES
from flavor.tile_catalog import catalog as native_catalog, effective, PROFILES, units

SCHEMA = "mosaic-flavor-v1"
NAME = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")


class FlavorError(ValueError):
    def __init__(self, message, *, path="document", tile_id=None):
        super().__init__(message)
        self.issues = [dict(path=path, message=message, tile_id=tile_id)]


def starter():
    cluster = tomllib.loads((CLUSTER / "mvp.toml").read_text())
    cluster["profile"] = fabric.PROFILE
    return dict(schema=SCHEMA, name="my_cgra", cluster=cluster)


def backend(cluster):
    return fabric if cluster.get("profile") == fabric.PROFILE else generator


def parse(text):
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FlavorError(str(error), path="toml") from error
    if document.get("schema") == "mosaic-cluster-v1":
        return dict(schema=SCHEMA, name="my_cgra", cluster=document)
    if document.get("schema") != SCHEMA:
        raise FlavorError(f"Expected {SCHEMA} or mosaic-cluster-v1", path="schema")
    return document


def dumps(document):
    """Serialize data, including editable drafts, without losing parameter overrides.

    Comments and original whitespace are not part of the architecture model.
    Quoted keys/strings prevent imported names from becoming TOML syntax.
    """
    lines = []

    def key_path(parts):
        return ".".join(json.dumps(part, ensure_ascii=False) for part in parts)

    def value(item):
        if type(item) is bool:
            return str(item).lower()
        if type(item) is int or isinstance(item, str):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, list) and not any(isinstance(x, dict) for x in item):
            return "[" + ", ".join(value(x) for x in item) + "]"
        raise FlavorError("TOML values must be strings, integers, booleans or arrays")

    def table(item, path=()):
        if not isinstance(item, dict):
            raise FlavorError("The architecture must be a table")
        for key, entry in item.items():
            if not isinstance(entry, dict) and not (
                    isinstance(entry, list) and entry and isinstance(entry[0], dict)):
                lines.append(f"{json.dumps(key, ensure_ascii=False)} = {value(entry)}")
        for key, entry in item.items():
            if isinstance(entry, dict):
                lines.extend(["", f"[{key_path((*path, key))}]"])
                table(entry, (*path, key))
            elif isinstance(entry, list) and entry and isinstance(entry[0], dict):
                for record in entry:
                    lines.extend(["", f"[[{key_path((*path, key))}]]"])
                    table(record, (*path, key))

    table(document)
    return "\n".join(lines) + "\n"


def resolve(document):
    if not isinstance(document, dict) or set(document) != {"schema", "name", "cluster"}:
        raise FlavorError("A flavor requires schema, name and cluster only")
    if document["schema"] != SCHEMA:
        raise FlavorError(f"Expected {SCHEMA}", path="schema")
    if not isinstance(document["name"], str) or not NAME.fullmatch(document["name"]):
        raise FlavorError("Use 1–40 lowercase letters, digits, underscores or hyphens; "
                          "start with a letter", path="name")
    cluster = document["cluster"]
    if not isinstance(cluster, dict):
        raise FlavorError("cluster must be a table", path="cluster")
    try:
        geometry = backend(cluster).validate(cluster)
    except (ValueError, KeyError, TypeError) as error:
        message = str(error)
        match = re.match(r"Tile (\d+)", message)
        raise FlavorError(message, path="cluster", tile_id=int(match[1]) if match else None) from error
    result = deepcopy(document)
    result["cluster"]["tiles"] = sorted(result["cluster"]["tiles"],
        key=lambda tile: (tile["row"], tile["col"]))
    for tile in result["cluster"]["tiles"]:
        tile["parameters"] = (effective(tile) if cluster["profile"] == fabric.PROFILE
                              else tile_parameters(tile))
    return result, geometry


def validate(document):
    try:
        resolved, geometry = resolve(document)
    except FlavorError as error:
        return dict(valid=False, issues=error.issues)
    cluster = resolved["cluster"]
    tiles = cluster["tiles"]
    return dict(valid=True, issues=[], resolved=resolved, summary=dict(
        tiles=len(tiles), bct=sum(t["class"] == "BCT" for t in tiles),
        mst=sum(t["class"] == "MST" for t in tiles),
        scratchpad_bytes=geometry["capacity"], data_width=geometry.get("data_width", 32),
        context_depth=4, validation_scope="native tile interfaces and grid transport" if
        cluster["profile"] == fabric.PROFILE else "full integration" if
        cluster["rows"] == cluster["cols"] == 2 else "control smoke"))


def catalog():
    return dict(schema=SCHEMA, dimensions=dict(minimum=1, rectangular=True), context_depth=4,
        configuration_guidance=ARCHITECTURE, guidance_scope=SCOPE,
        constraints=["Positive row and column counts", "One tile per position", "One clock domain"],
        tile_classes=[dict(id=kind, available=True,
            title=title, description=description, guidance=TILES[kind],
            profiles=PROFILES[kind], functional_units=units(kind),
            parameters=native_catalog()[kind]) for kind, title, description in (
                ("BCT", "Basic compute", "Scalar ALU, multiply and MAC profiles"),
                ("MST", "Memory service", "Load/store engines and scratchpad access"),
                ("VCT", "Vector compute", "Vector lanes, reduction and dot product"),
                ("SFT", "Special functions", "LUT, polynomial, reciprocal, RSQRT and exponential"),
                ("CPT", "Control processing", "Predicates, loops, events and tagged actions"))])
