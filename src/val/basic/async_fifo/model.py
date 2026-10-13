"""Independent accepted-record queue and destination-edge visibility history."""

from collections import deque
from dataclasses import dataclass, field


@dataclass
class DomainHistory:
    """Unbounded handshake count; modulo arithmetic is used only at interfaces."""
    count: int = 0
    up: bool = False
    saw_peer: bool = False
    samples: list[tuple[int, bool]] = field(default_factory=list)
    level: int = 0
    boundary: bool = True

    def visible(self, stage: int) -> tuple[int, bool]:
        # Each history entry is what existed at a destination rising edge,
        # before either source can update at a coincident edge.
        return self.samples[-stage] if len(self.samples) >= stage else (0, False)

    def reset(self):
        self.count, self.up, self.saw_peer = 0, False, False
        self.samples.clear()
        self.level, self.boundary = 0, True

    def advance(self, peer, stages, transfer, depth, *, write):
        visible_count, visible_up = self.visible(stages)
        initialized = self.up and visible_up
        self.count += int(transfer)
        self.level = ((self.count - visible_count) if write else (visible_count - self.count)) % (2 * depth) if initialized else 0
        self.boundary = (self.level == depth if write else self.level == 0) if initialized else True
        if not self.saw_peer:
            self.up = True
        elif not visible_up:
            self.up = False
        self.saw_peer |= visible_up
        self.samples.append(peer)


class QueueModel:
    """Only observed external handshakes add/remove four-state records."""
    def __init__(self):
        self.records = deque()
        self.w, self.r = DomainHistory(), DomainHistory()
        self.epoch = False
        self.pushed = self.popped = self.canceled = 0
        self.previous_resets = (1, 1)

    def reset_event(self, resets):
        new_reset = any(old and not new for old, new in zip(self.previous_resets, resets))
        if new_reset:
            self.canceled += len(self.records)
            self.records.clear()
            self.epoch = False
        if resets == (0, 0):
            self.epoch = True
        for domain, released in zip((self.w, self.r), resets):
            if not released:
                domain.reset()
        self.previous_resets = resets
        return new_reset

    def transfer(self, push, pop, data, observed):
        if not self.epoch:
            self.canceled += int(push)
            self.pushed += int(push)
            return
        # Read before write: a simultaneous write cannot legitimize underflow.
        if pop:
            assert self.records, "FIFO underflow: pop without an accepted record"
            expected = self.records.popleft()
            assert observed == expected, f"FIFO ordering/data assertion failed: expected {expected}, got {observed}"
            self.popped += 1
        if push:
            self.records.append(data)
            self.pushed += 1
