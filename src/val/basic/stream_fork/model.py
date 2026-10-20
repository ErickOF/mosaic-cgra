"""Independent per-output acceptance queues and delivery/cancellation ledgers."""

from collections import deque
from dataclasses import dataclass
from mosaic_uvm.logic import bits


def known(word):
    return set(word) <= {'0', '1'}


def lane(word, index, width):
    end = len(word)-index*width
    return word[end-width:end]


@dataclass(frozen=True)
class Copy:
    identifier: int
    data: str
    accepted_edge: int


class StreamForkModel:
    def __init__(self, config):
        self.config = config
        self.queues = [deque() for _ in range(config.outputs)]
        self.accepted = [0]*config.outputs
        self.consumed = [0]*config.outputs
        self.discarded = [0]*config.outputs
        self.initialized = False
        self.edge = self.transactions = 0
        self.raw_data = None
        self.selection = 0
        self.delivery_order = []

    @property
    def pending(self):
        return sum(1 << k for k, queue in enumerate(self.queues) if queue)

    def reset(self):
        for k, queue in enumerate(self.queues):
            self.discarded[k] += len(queue)
            queue.clear()
        self.selection = 0
        self.delivery_order = []
        self.initialized = True

    def outputs(self, ports):
        ready = all(not queue or ports['i_ready'][-k-1] == '1' for k, queue in enumerate(self.queues))
        return dict(o_ready=str(int(ready)), o_valid=bits(self.pending, self.config.outputs),
            o_data=''.join(queue[0].data if queue else '0'*self.config.width for queue in reversed(self.queues)))

    def step(self, ports):
        self.edge += 1
        before, selection = self.pending, self.selection
        popped = []
        for k, queue in enumerate(self.queues):
            if queue and ports['i_ready'][-k-1] == '1':
                token = queue.popleft()
                assert token.accepted_edge < self.edge, 'One-cycle latency assertion failed'
                assert lane(ports['o_data'], k, self.config.width) == token.data, 'Consumed-copy ordering assertion failed'
                self.consumed[k] += 1
                popped.append(k)
        if popped:
            self.delivery_order.append(tuple(popped))
        complete = before != 0 and self.pending == 0
        order = tuple(self.delivery_order) if complete else ()
        push = ports['i_valid'] == '1' and self.pending == 0
        destination = int(ports['i_destination'], 2) if self.config.masked and push else self.config.all_outputs
        if push:
            self.transactions += 1
            token = Copy(self.transactions, ports['i_data'], self.edge)
            for k, queue in enumerate(self.queues):
                if destination & (1 << k):
                    queue.append(token)
                    self.accepted[k] += 1
            self.selection = destination
            self.delivery_order = []
            self.raw_data = ports['i_data']
        elif complete:
            self.selection = 0
            self.delivery_order = []
        self.conservation()
        return dict(before=before, after=self.pending, selection=selection, push=push, destination=destination,
            popped=popped, complete=complete, order=order, data=ports['i_data'])

    def conservation(self):
        identities = set()
        for k, queue in enumerate(self.queues):
            assert len(queue) <= 1, 'Per-output capacity assertion failed'
            assert self.accepted[k] == self.consumed[k]+self.discarded[k]+len(queue), 'Copy-conservation assertion failed'
            identities.update(copy.identifier for copy in queue)
        assert len(identities) <= 1, 'More than one active multicast transaction'

    def ledger(self):
        return [dict(accepted=self.accepted[k], consumed=self.consumed[k], discarded=self.discarded[k],
            pending=len(queue)) for k, queue in enumerate(self.queues)]
