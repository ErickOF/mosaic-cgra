"""Independent event admission/order model with an exact accepted-record ledger."""
from collections import deque

FIELDS = ('type', 'source_id', 'owner_id', 'kernel_id', 'context_id', 'package_id',
          'epoch', 'payload', 'severity', 'sequence')


class EventLedger:
    def __init__(self, tiles, depth, ids):
        self.tiles, self.depth, self.ids = tiles, depth, ids
        self.queue = deque()
        self.cursor = 0
        self.pending = None
        self.sequence = 0
        self.completed = 0
        self.duplicate = False
        self.failed = self.exhausted = self.queue_failed = False
        self.completion_failed = False
        self.arbiter_failed = False
        self.accepted = self.delivered = 0

    def candidate(self, p):
        requests = p['i_tile_valid'] or 0
        selected = self.pending
        if selected is not None and p['i_tile_valid'] is not None and not (requests >> selected & 1):
            selected = None
            unavailable_pending = True
        else:
            unavailable_pending = False
        if selected is None and not unavailable_pending:
            selected = next((t for offset in range(self.tiles)
                             if requests >> (t := (self.cursor + offset) % self.tiles) & 1), None)
        record = dict.fromkeys(FIELDS, 0)
        for field in ('owner_id', 'kernel_id', 'context_id', 'package_id', 'epoch'):
            record[field] = p['i_' + field]
        record['sequence'] = self.sequence
        source = None
        if p['i_fault_valid'] == 1:
            source = 'fault'
            record |= dict(type=3, source_id=p['i_fault_source'], payload=p['i_fault_code'], severity=3)
        elif p['i_terminal_valid'] == 1:
            source = 'terminal'
            record |= dict(type=2, source_id=255, payload=self.completed)
        elif p['i_memory_valid'] == 1:
            source = 'memory'
            record |= dict(type=1, source_id=254, payload=p['i_memory_payload'])
        elif selected is not None:
            source = selected
            payload = p['i_tile_payload']
            record |= dict(source_id=self.ids[selected],
                           payload=None if payload is None else payload >> (selected * 256) & ((1 << 256)-1))
        return source, selected, record

    def step(self, p, *, corruption=None):
        """Return expected combinational pins, then retire the modeled AON edge."""
        if corruption == 'queue':
            self.queue_failed = True
        if corruption == 'completion':
            self.completion_failed = True
        withdrawn = self.pending is not None and p['i_tile_valid'] is not None and not (
            p['i_tile_valid'] >> self.pending & 1)
        source, selected, record = self.candidate(p)
        controls = ('i_tile_valid', 'i_fault_valid', 'i_terminal_valid',
                    'i_memory_valid', 'i_clear_completion')
        input_bad = any(p[name] is None for name in controls) or (
            source is not None and any(v is None for v in record.values()))
        failure = self.failed or self.exhausted or self.queue_failed or self.completion_failed or self.arbiter_failed or input_bad
        valid = bool(self.queue) and not self.queue_failed
        pop = valid and p['i_event_ready'] == 1
        ready = (len(self.queue) < self.depth or pop) and not failure
        expected = dict(o_event_valid=int(valid), o_error=int(failure),
                        o_empty=int(not self.queue and not failure),
                        o_fault_ready=int(ready),
                        o_terminal_ready=int(ready and not p['i_fault_valid']),
                        o_memory_ready=int(ready and not p['i_fault_valid'] and not p['i_terminal_valid']))
        tile_selected = isinstance(source, int)
        expected['o_tile_ready'] = 1 << source if ready and tile_selected else 0
        if not self.completion_failed:
            expected |= dict(o_completion_mask=self.completed, o_duplicate_completion=int(self.duplicate))
        output = self.queue[0] if valid else dict.fromkeys(FIELDS, 0)
        expected |= {'o_event_' + name: value for name, value in output.items()}
        if pop:
            self.queue.popleft()
            self.delivered += 1
        admitted = source is not None and ready
        if admitted:
            self.queue.append(record)
            self.accepted += 1
            self.sequence += 1
            self.exhausted = self.sequence == 1 << 32
        if not failure:
            if p['i_clear_completion']:
                self.completed = 0
            if admitted and tile_selected:
                self.cursor = (source + 1) % self.tiles
                self.pending = None
                if record['payload'] & 7 == 0:
                    self.duplicate |= bool(self.completed >> source & 1)
                    self.completed |= 1 << source
            elif selected is not None:
                self.pending = selected
        self.failed |= failure
        self.arbiter_failed |= withdrawn
        return expected, source if admitted else None, bool(pop and admitted)

    def drained(self):
        assert not self.queue, 'Accepted event records have not retired'
        assert self.accepted == self.delivered, 'Event loss or duplicate delivery'
