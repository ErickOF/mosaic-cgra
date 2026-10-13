"""Clock events, immutable port snapshots, and synchronizer fault requests."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


INPUTS = ("i_w_clk", "i_r_clk", "i_w_rstb", "i_r_rstb", "i_w_valid", "i_r_ready", "i_w_data")
OUTPUTS = ("o_w_ready", "o_w_full", "o_w_almost_full", "o_w_level", "o_w_init_done",
           "o_r_valid", "o_r_data", "o_r_empty", "o_r_almost_empty", "o_r_level", "o_r_init_done")
CHAINS = ("r_gray_sync", "w_gray_sync", "r_up_sync", "w_up_sync")
INTERNALS = ("w_bin", "r_bin", "w_gray", "r_gray", "w_up", "r_up")


class AsyncFifoItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, delay_ps=100, relation="manual", random=False,
                 fault=None, cancellation=False):
        super().__init__(label)
        assert delay_ps >= 4
        self.inputs = dict(inputs)
        self.delay_ps, self.relation, self.random = delay_ps, relation, random
        self.fault, self.cancellation = fault, cancellation
        self.observation = None


@dataclass(frozen=True)
class Snapshot:
    ports: dict[str, str]
    internals: dict[str, str]
    chains: dict[str, tuple[str, ...]]

    def integer(self, name: str) -> int:
        value = self.ports[name]
        assert set(value) <= {"0", "1"}, f"Known-control assertion failed: {name}={value}"
        return int(value, 2)


@dataclass(frozen=True)
class Observation:
    before: Snapshot
    after: Snapshot
    time_ps: int
    item: AsyncFifoItem


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    allowed: bool
