"""Positional unit-stream oracle and independent transfer/cancellation ledgers.

The functional reference stores accepted transfer units, including explicit holes,
not an RTL assembly word. Packing groups records, serialization queues slices,
and every consumed unit and packet boundary is conserved across cancellation.
Raw storage is a separate write-enable oracle, never a functional source.
"""

from collections import deque
from dataclasses import dataclass
from mosaic_uvm.logic import bits


def known(word):
    return set(word) <= {'0', '1'}


def lane(word, index, width):
    end = len(word) - index * width
    return word[end-width:end]


def units(data, keep, width):
    return tuple(lane(data, k, width) if bit == '1' else None for k, bit in enumerate(reversed(keep)))


def payload(record, width):
    return dict(o_data=''.join(unit if unit is not None else '0'*width for unit in reversed(record.units)),
        o_keep=''.join(str(int(unit is not None)) for unit in reversed(record.units)),
        o_last=record.last, o_user=record.user)


@dataclass(frozen=True)
class Beat:
    units: tuple[str | None, ...]
    last: str
    user: str
    accepted_edge: int
    sequence: int = 0
    terminal: int = 0


class WidthConverterModel:
    def __init__(self, config):
        self.config = config
        self.queue, self.partial = deque(), []
        self.initialized = False
        self.edge = self.accepted = self.consumed = 0
        self.input_units = self.output_units = self.discarded_units = 0
        self.input_last = self.output_last = self.discarded_last = 0
        self.raw = {}

    @property
    def busy(self):
        return bool(self.queue or self.partial)

    @property
    def position(self):
        return len(self.partial) if self.config.mode == 'pack' else self.queue[0].sequence if self.queue else 0

    def reset(self):
        self.discarded_units += sum(unit is not None for beat in (*self.queue, *self.partial) for unit in beat.units)
        self.discarded_last += sum(beat.last == '1' for beat in (*self.queue, *self.partial))
        self.queue.clear()
        self.partial.clear()
        self.initialized = True

    def ready(self, ports):
        # Queue depth is the number of future output beats, not an RTL count.
        return not self.queue or ports['i_ready'] == '1' and (self.config.mode != 'unpack' or len(self.queue) == 1)

    def outputs(self, ports):
        c = self.config
        enabled = ports['i_rstb'] == '1' and ports['i_flush'] == '0'
        live = enabled and bool(self.queue)
        result = dict(o_ready=str(int(enabled and self.ready(ports))), o_valid=str(int(live)),
            o_busy=str(int(enabled and self.busy)), o_data='0'*c.output_width, o_keep='0'*c.out_units,
            o_last='0', o_user='0'*c.user_width)
        if live:
            result.update(payload(self.queue[0], c.unit_width))
        return result

    def update_raw(self, ports, accepted, position):
        if not self.raw or not accepted:
            return
        c = self.config
        offset = (position if c.lsb_first else c.ratio-1-position)*c.in_units if c.mode == 'pack' else 0
        data = list(reversed(self.raw['buffered_data']))
        keep = list(reversed(self.raw['buffered_keep'])) if c.mode == 'pack' and position else ['0']*c.wide_units
        for k in range(c.in_units):
            keep[offset+k] = ports['i_keep'][-k-1]
            if keep[offset+k] == '1':
                start = (offset+k)*c.unit_width
                data[start:start+c.unit_width] = reversed(lane(ports['i_data'], k, c.unit_width))
        self.raw.update(buffered_data=''.join(reversed(data)), buffered_keep=''.join(reversed(keep)),
            buffered_last=ports['i_last'])
        if c.mode != 'pack' or position == 0:
            self.raw['buffered_user'] = ports['i_user']

    def step(self, ports):
        c = self.config
        self.edge += 1
        position, before, busy = self.position, len(self.queue), self.busy
        push = ports['i_valid'] == '1' and self.ready(ports)
        pop = bool(self.queue) and ports['i_ready'] == '1'
        consumed = self.queue.popleft() if pop else None
        if consumed:
            assert consumed.accepted_edge < self.edge, 'Registered latency assertion failed'
            assert {name: ports[name] for name in ('o_data', 'o_keep', 'o_last', 'o_user')} == payload(consumed, c.unit_width), 'Consumed unit/order assertion failed'
            self.consumed += 1
            self.output_units += sum(unit is not None for unit in consumed.units)
            self.output_last += consumed.last == '1'
        if push:
            incoming = Beat(units(ports['i_data'], ports['i_keep'], c.unit_width), ports['i_last'], ports['i_user'], self.edge)
            self.accepted += 1
            self.input_units += sum(unit is not None for unit in incoming.units)
            self.input_last += incoming.last == '1'
            if c.mode == 'pack':
                if self.partial:
                    assert incoming.user == self.partial[0].user, 'Protocol assertion failed: metadata_match'
                self.partial.append(incoming)
                if len(self.partial) == c.ratio or incoming.last == '1':
                    slices = [beat.units for beat in self.partial] + [(None,)*c.in_units]*(c.ratio-len(self.partial))
                    if not c.lsb_first:
                        slices.reverse()
                    self.queue.append(Beat(tuple(unit for chunk in slices for unit in chunk), incoming.last,
                        self.partial[0].user, self.edge))
                    self.partial.clear()
            elif c.mode == 'unpack':
                slices = [incoming.units[k:k+c.out_units] for k in range(0, c.in_units, c.out_units)]
                if not c.lsb_first:
                    slices.reverse()
                if incoming.last == '1':
                    while len(slices) > 1 and all(unit is None for unit in slices[-1]):
                        slices.pop()
                for k, chunk in enumerate(slices):
                    self.queue.append(Beat(chunk, str(int(incoming.last == '1' and k == len(slices)-1)),
                        incoming.user, self.edge, k, len(slices)-1))
            else:
                self.queue.append(incoming)
        self.update_raw(ports, push, position)
        self.conservation()
        return dict(push=push, pop=pop, before=before, busy=busy, position=position,
            consumed=consumed, incoming=incoming if push else None, after=len(self.queue),
            completion=push and bool(self.queue), terminal=self.queue[-1].terminal if push and self.queue else None)

    def conservation(self):
        pending = (*self.queue, *self.partial)
        assert self.input_units == self.output_units + self.discarded_units + sum(unit is not None for beat in pending for unit in beat.units), 'Unit conservation assertion failed'
        assert self.input_last == self.output_last + self.discarded_last + sum(beat.last == '1' for beat in pending), 'Boundary conservation assertion failed'
        assert len(self.queue) <= (self.config.ratio if self.config.mode == 'unpack' else 1), 'Output capacity assertion failed'
        assert len(self.partial) < self.config.ratio, 'Collection capacity assertion failed'

    def ledger(self):
        return dict(accepted_beats=self.accepted, consumed_beats=self.consumed, accepted_units=self.input_units,
            consumed_units=self.output_units, discarded_units=self.discarded_units, accepted_last=self.input_last,
            consumed_last=self.output_last, discarded_last=self.discarded_last, pending_units=sum(
                unit is not None for beat in (*self.queue, *self.partial) for unit in beat.units), busy=self.busy)
