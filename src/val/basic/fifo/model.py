"""Independent accepted-item queue; no prediction from DUT pointers or data."""

from collections import deque
from mosaic_uvm.logic import bits
from fifo.transaction import CONTROLS


def protocol_violation(ports):
    return next((name for name in CONTROLS if ports[name] not in ('0', '1')), None)


class FifoModel:
    def __init__(self, config):
        self.config = config
        self.queue = deque()
        self.read = self.write = 0
        self.initialized = False

    def reset(self):
        self.queue.clear()
        self.read = self.write = 0
        self.initialized = True

    def outputs(self, ports):
        count, depth = len(self.queue), self.config.depth
        return dict(o_ready=bits(int(count < depth or (count > 0 and ports['i_ready'] == '1')), 1),
                    o_valid=bits(int(count > 0), 1), o_data=self.queue[0] if count else '0' * self.config.width,
                    o_empty=bits(int(count == 0), 1), o_full=bits(int(count == depth), 1),
                    o_almost_full=bits(int(count >= self.config.almost_full), 1),
                    o_almost_empty=bits(int(count <= self.config.almost_empty), 1),
                    o_occupancy=bits(count, depth.bit_length()))

    def step(self, ports):
        count = len(self.queue)
        pop = count > 0 and ports['i_ready'] == '1'
        push = ports['i_valid'] == '1' and (count < self.config.depth or pop)
        event = dict(count=count, push=int(push), pop=int(pop), read=self.read, write=self.write,
                     consumed=self.queue[0] if pop else None,
                     read_wrap=int(pop and self.read == self.config.depth - 1),
                     write_wrap=int(push and self.write == self.config.depth - 1))
        if pop:
            self.queue.popleft()
            self.read = (self.read + 1) % self.config.depth
        if push:
            self.queue.append(ports['i_data'])
            self.write = (self.write + 1) % self.config.depth
        return event
