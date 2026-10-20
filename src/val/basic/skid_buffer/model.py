"""Independent accepted-item queue, including same-edge bypass and reset discards."""

from collections import deque
from dataclasses import dataclass


def known(word):
    return set(word) <= {'0', '1'}


@dataclass(frozen=True)
class Token:
    data: str
    edge: int


class SkidBufferModel:
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
        occupied = bool(self.queue) and not (self.config.asynchronous and ports['i_rstb'] == '0')
        return dict(o_ready=str(int(not occupied)), o_valid=str(int(occupied or ports['i_valid'] == '1')),
            o_data=self.queue[0].data if occupied else ports['i_data'] if ports['i_valid'] == '1' else '0'*self.config.width)

    def step(self, ports):
        self.edge += 1
        occupied = bool(self.queue)
        push = ports['i_valid'] == '1' and not occupied
        pop = (occupied or ports['i_valid'] == '1') and ports['i_ready'] == '1'
        # Append before consuming: an empty bypass is accepted and consumed on
        # this same edge. A buffered release admits no same-edge replacement.
        if push:
            self.queue.append(Token(ports['i_data'], self.edge))
            self.accepted += 1
        token = self.queue.popleft() if pop else None
        if pop:
            assert token.edge <= self.edge
            assert (token.edge == self.edge) == (not occupied), 'Bypass/release edge assertion failed'
            self.consumed += 1
        capture = push and not pop
        if capture:
            self.raw_data = ports['i_data']
        self.conservation()
        operation = 'release' if occupied and pop else 'hold' if occupied else 'bypass' if pop else 'capture' if push else 'idle'
        return dict(occupied=int(occupied), push=push, pop=pop, capture=capture,
            consumed=token.data if token else None, operation=operation)

    def conservation(self):
        assert len(self.queue) <= 1, 'Capacity assertion failed'
        assert self.accepted == self.consumed + self.discarded + len(self.queue), 'Token-conservation assertion failed'
