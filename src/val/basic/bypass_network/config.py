"""Expected static graph, timing profile, and reproducible campaign settings."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import product
import os
from pathlib import Path

from cocotb.utils import get_time_from_sim_steps


def connectivity(sources: int, destinations: int, profile: str) -> int:
    """Unit-test graphs, without inventing architectural source identifiers."""
    mask = 0
    for destination in range(destinations):
        match profile:
            case "minimal":
                edges = {0, destination % sources}
            case "balanced":
                edges = {0, destination % sources, (destination + 1) % sources}
            case "flexible":
                edges = set(range(sources)) - ({1 + destination % (sources - 1)} if sources > 1 else set())
            case "all":
                edges = set(range(sources))
            case _:
                raise ValueError(f"Unknown connectivity profile: {profile}")
        for source in edges:
            mask |= 1 << (destination * sources + source)
    return mask


@dataclass(frozen=True)
class BypassNetworkConfig:
    width: int
    sources: int
    destinations: int
    mask: int
    registered: bool
    async_reset: bool
    seed: int
    random_cycles: int
    check_internals: bool
    graph: str
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls) -> BypassNetworkConfig:
        sources = int(os.getenv("BYPASS_NETWORK_NUM_SOURCES", "8"))
        destinations = int(os.getenv("BYPASS_NETWORK_NUM_DESTINATIONS", "4"))
        registered = int(os.getenv("BYPASS_NETWORK_REGISTER_OUTPUTS", "0"))
        asynchronous = int(os.getenv("BYPASS_NETWORK_ASYNC_RESET", "0"))
        structural = int(os.getenv("BYPASS_NETWORK_CHECK_INTERNALS", "1"))
        assert registered in (0, 1) and asynchronous in (0, 1) and structural in (0, 1)
        report = Path(os.getenv("COCOTB_RESULTS_FILE", "build/bypass_network/results.xml")).with_name("coverage.json")
        config = cls(
            width=int(os.getenv("BYPASS_NETWORK_DATA_WIDTH", "32")), sources=sources, destinations=destinations,
            mask=int(os.getenv("BYPASS_NETWORK_CONNECTIVITY_MASK", str((1 << (sources * destinations)) - 1)), 0),
            registered=bool(registered), async_reset=bool(asynchronous),
            seed=int(os.getenv("BYPASS_NETWORK_SEED", "20261012")),
            random_cycles=int(os.getenv("BYPASS_NETWORK_RANDOM_CYCLES", "2000")),
            check_internals=bool(structural), graph=os.getenv("BYPASS_NETWORK_GRAPH", "custom"),
            probe=os.getenv("BYPASS_NETWORK_ASSERTION_PROBE", ""),
            coverage_file=Path(os.getenv("BYPASS_NETWORK_COVERAGE_FILE", str(report))),
        )
        assert config.width >= 1 and sources >= 1 and destinations >= 1
        assert 0 <= config.mask < 1 << (sources * destinations)
        assert all(config.connected(destination) for destination in range(destinations))
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv("TEST_SETTLE_NS", "0")) == 0, "This suite verifies zero-delay RTL; use TEST_SETTLE_NS=0"
        assert get_time_from_sim_steps(1, unit="ps") <= 1, "Use 1 ps precision or finer"
        return config

    @property
    def select_width(self) -> int:
        return max(1, (self.sources - 1).bit_length())

    @property
    def parameters(self) -> dict[str, int]:
        return dict(DATA_WIDTH=self.width, NUM_SOURCES=self.sources, NUM_DESTINATIONS=self.destinations,
                    CONNECTIVITY_MASK=self.mask, REGISTER_OUTPUTS=int(self.registered), ASYNC_RESET=int(self.async_reset))

    def connected(self, destination: int) -> tuple[int, ...]:
        return tuple(source for source in range(self.sources) if self.mask >> (destination * self.sources + source) & 1)

    @property
    def edges(self) -> set[tuple[int, int]]:
        return {(destination, source) for destination in range(self.destinations) for source in self.connected(destination)}

    @property
    def disconnected(self) -> set[tuple[int, int]]:
        return set(product(range(self.destinations), range(self.sources))) - self.edges

    @property
    def maximum_fanout(self) -> int:
        return max(sum((destination, source) in self.edges for destination in range(self.destinations)) for source in range(self.sources))

    def distinct_assignment(self) -> dict[int, int]:
        """Maximum bipartite matching; unreachable population bins are graph-specific."""
        owner = {}

        def assign(destination, visited):
            for source in self.connected(destination):
                if source in visited:
                    continue
                visited.add(source)
                if source not in owner or assign(owner[source], visited):
                    owner[source] = destination
                    return True
            return False

        for destination in range(self.destinations):
            assign(destination, set())
        return {destination: source for source, destination in owner.items()}

    @property
    def unknown_selects(self) -> tuple[str, ...]:
        return tuple(word for states in product("01xz", repeat=self.select_width)
                     if set(word := "".join(states)) & {"x", "z"})
