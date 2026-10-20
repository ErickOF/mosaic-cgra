"""Independent acceptance queue with reset cancellation and token conservation."""

from collections import deque
from dataclasses import dataclass
from mosaic_uvm.logic import bits


def known(word):
    return set(word) <= {'0', '1'}


@dataclass(frozen=True)
class Token:
    data: str
    accepted_edge: int


class RegisterSliceModel:
    def __init__(self, config):
        self.config = config
        self.queue = deque()
        self.initialized = False
        self.edge = self.accepted = self.consumed = self.discarded = 0
        self.raw_data = None

    def reset(self):
        self.discarded += len(self.queue)
        self.queue.clear()
        self.initialized = True

    def outputs(self, ports):
        return dict(o_ready=bits(int(not self.queue or ports['i_ready'] == '1'), 1),
            o_valid=bits(int(bool(self.queue)), 1),
            o_data=self.queue[0].data if self.queue else '0'*self.config.width)

    def step(self, ports):
        self.edge += 1
        occupied = bool(self.queue)
        pop = occupied and ports['i_ready'] == '1'
        push = ports['i_valid'] == '1' and (not occupied or pop)
        token = self.queue.popleft() if pop else None
        if pop:
            assert token.accepted_edge < self.edge, 'One-cycle latency assertion failed'
            self.consumed += 1
        if push:
            self.queue.append(Token(ports['i_data'], self.edge))
            self.raw_data = ports['i_data']
            self.accepted += 1
        self.conservation()
        operation = 'replace' if push and pop else 'fill' if push else 'consume' if pop else 'hold' if occupied else 'idle'
        return dict(occupied=int(occupied), push=push, pop=pop, consumed=token.data if token else None, operation=operation)

    def conservation(self):
        assert len(self.queue) <= 1, 'Capacity assertion failed'
        assert self.accepted == self.consumed + self.discarded + len(self.queue), 'Token-conservation assertion failed'
