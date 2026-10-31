"""Strict scalar/table configuration and native port dimensions."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
import os
from configuration_network.defaults import DEFAULTS, PORTS, TABLE_WIDTHS
from configuration_network.layout import dimensions, tables


@dataclass(frozen=True)
class NetworkConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = {
            n: int(os.getenv("CONFIGURATION_NETWORK_" + n, str(v)), 0)
            for n, v in DEFAULTS.items()
        }
        for n in TABLE_WIDTHS:
            if "CONFIGURATION_NETWORK_" + n in os.environ:
                p[n] = int(os.environ["CONFIGURATION_NETWORK_" + n], 0)
        p.update(tables(p))
        return cls(
            p,
            int(os.getenv("CONFIGURATION_NETWORK_SEED", "20261026")),
            int(os.getenv("CONFIGURATION_NETWORK_RANDOM_CYCLES", "1000")),
            Path(
                os.getenv(
                    "CONFIGURATION_NETWORK_COVERAGE_FILE",
                    "build/configuration_network/coverage.json",
                )
            ),
        )

    @cached_property
    def aliases(self):
        return dimensions(self.parameters)

    @cached_property
    def widths(self):
        return {
            n: eval(w, {"__builtins__": {}}, self.aliases)
            for n, (_, w) in PORTS.items()
        }
