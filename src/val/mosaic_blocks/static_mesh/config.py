"""Environment parameters and exact public widths."""

from dataclasses import dataclass
import os
from pathlib import Path
from static_mesh.defaults import DEFAULTS, PORTS
from static_mesh.topology import dimensions, physical


@dataclass(frozen=True)
class MeshConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = {n: int(os.getenv("STATIC_MESH_" + n, str(v)), 0) for n, v in DEFAULTS.items()}
        for n in ("NODE_PRESENT_MASK", "LINK_PRESENT_MASK", "NODE_CONNECTIVITY_MASKS"):
            if "STATIC_MESH_" + n in os.environ:
                p[n] = int(os.environ["STATIC_MESH_" + n], 0)
        g = physical(p)
        p.update(
            NODE_PRESENT_MASK=g["nodes"],
            LINK_PRESENT_MASK=g["mask"],
            NODE_CONNECTIVITY_MASKS=g["connectivity"],
        )
        return cls(
            p,
            int(os.getenv("STATIC_MESH_SEED", "20261025")),
            int(os.getenv("STATIC_MESH_RANDOM_CYCLES", "1000")),
            Path(os.getenv("STATIC_MESH_COVERAGE_FILE", "build/static_mesh/coverage.json")),
        )

    @property
    def aliases(self):
        return dimensions(self.parameters)

    @property
    def widths(self):
        return {n: eval(w, {"__builtins__": {}}, self.aliases) for n, (_, w) in PORTS.items()}
