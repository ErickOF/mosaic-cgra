"""Strict parameter and port geometry from the executable contract."""

from dataclasses import dataclass
from pathlib import Path
import os
from predicate_network.defaults import DEFAULTS, PORTS
from predicate_network.topology import dimensions, physical


@dataclass(frozen=True)
class PredicateConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = {n: int(os.getenv("PREDICATE_NETWORK_" + n, str(v)), 0) for n, v in DEFAULTS.items()}
        for n in ("NODE_PRESENT_MASK", "LINK_PRESENT_MASK", "NODE_CONNECTIVITY_MASKS"):
            if "PREDICATE_NETWORK_" + n in os.environ:
                p[n] = int(os.environ["PREDICATE_NETWORK_" + n], 0)
        g = physical(p)
        p.update(
            NODE_PRESENT_MASK=g["nodes"],
            LINK_PRESENT_MASK=g["mask"],
            NODE_CONNECTIVITY_MASKS=g["connectivity"],
        )
        return cls(
            p,
            int(os.getenv("PREDICATE_NETWORK_SEED", "20261025")),
            int(os.getenv("PREDICATE_NETWORK_RANDOM_CYCLES", "1000")),
            Path(
                os.getenv(
                    "PREDICATE_NETWORK_COVERAGE_FILE", "build/predicate_network/coverage.json"
                )
            ),
        )

    @property
    def aliases(self):
        return dimensions(self.parameters)

    @property
    def widths(self):
        return {n: eval(w, {"__builtins__": {}}, self.aliases) for n, (_, w) in PORTS.items()}
