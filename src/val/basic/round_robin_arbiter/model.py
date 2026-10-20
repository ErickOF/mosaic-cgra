"""Independent cyclic-priority list, ownership history and four-state semantics."""

from mosaic_uvm.logic import bits
from round_robin_arbiter.config import PAYLOAD_WIDTH


def known(word):
    return set(word) <= {'0', '1'}


def bit(word, index):
    return word[-index-1]


def qualify(a, b):
    return '0' if '0' in (a, b) else '1' if a == b == '1' else 'x'


def payload(ports, index):
    packed = ports['i_payload']
    return packed[len(packed)-(index+1)*PAYLOAD_WIDTH:len(packed)-index*PAYLOAD_WIDTH]


class ArbiterModel:
    def __init__(self, config):
        self.config = config
        self.initialized = False
        self.reset()
        self.initialized = False

    def reset(self):
        c = self.config
        self.order = list(range(c.initial, c.requesters)) + list(range(c.initial))
        self.pending = None
        self.pending_index = self.pending_lock = 0
        self.pending_payload = None
        self.owner = None
        self.owner_storage = 0
        self.error = False
        self.receiver = None
        self.waits = [0]*c.requesters
        self.initialized = True

    @property
    def state_class(self):
        return 'error' if self.error else 'locked_pending' if self.owner is not None and self.pending else 'locked' if self.owner is not None else 'pending' if self.pending else 'idle'

    def active(self, ports):
        return [qualify(bit(ports['i_request'], r), bit(ports['i_eligible'], r)) for r in range(self.config.requesters)]

    def errors(self, ports):
        if ports['i_rstb'] == '0' or ports['i_flush'] == '1' or self.error:
            return set()
        found = set()
        if self.pending:
            index, lock = self.pending
            if bit(ports['i_request'], index) == '0': found.add('pending_request')
            if bit(ports['i_eligible'], index) == '0': found.add('pending_eligibility')
            if self.config.has_lock and bit(ports['i_lock'], index) in '01' and int(bit(ports['i_lock'], index)) != lock:
                found.add('pending_lock')
        if self.owner is not None:
            if bit(ports['i_eligible'], self.owner) == '0': found.add('owner_eligibility')
            if bit(ports['i_request'], self.owner) == bit(ports['i_lock'], self.owner) == '0': found.add('owner_gap_release')
        if not self.config.has_lock and '1' in ports['i_lock']:
            found.add('lock_disabled')
        return found

    def selection(self, ports):
        if ports['i_rstb'] == '0' or ports['i_flush'] == '1' or self.error or self.errors(ports):
            return None, 0
        if self.pending:
            index, lock = self.pending
            controls = (bit(ports['i_request'], index), bit(ports['i_eligible'], index))
            if self.config.has_lock:
                controls += (bit(ports['i_lock'], index),)
            return (index, lock) if all(value in '01' for value in controls) else ('x', 'x')
        if self.owner is not None:
            active = self.active(ports)[self.owner]
            if active == '0': return None, 0
            if active == 'x': return 'x', 'x'
            lock = bit(ports['i_lock'], self.owner)
            return self.owner, int(lock) if lock in '01' else lock
        active = self.active(ports)
        for index in self.order:
            if active[index] == 'x': return 'x', 'x'
            if active[index] == '1':
                lock = bit(ports['i_lock'], index) if self.config.has_lock else '0'
                return index, int(lock) if lock in '01' else lock
        return None, 0

    def unknown_violation(self, ports):
        for name in ('i_rstb', 'i_flush', 'i_accept'):
            if not known(ports[name]): return name
        if ports['i_rstb'] == '0' or ports['i_flush'] == '1' or self.error:
            return None
        if not self.config.has_lock and not known(ports['i_lock']): return 'i_lock'
        if self.pending:
            index = self.pending[0]
            for name in ('i_request', 'i_eligible', 'i_lock') if self.config.has_lock else ('i_request', 'i_eligible'):
                if bit(ports[name], index) not in '01': return name
        elif self.owner is not None:
            for name in ('i_request', 'i_eligible', 'i_lock'):
                if bit(ports[name], self.owner) not in '01': return name
        else:
            for index in self.order:
                active = self.active(ports)[index]
                if active == 'x':
                    return 'i_request' if bit(ports['i_request'], index) not in '01' else 'i_eligible'
                if active == '1':
                    if self.config.has_lock and bit(ports['i_lock'], index) not in '01': return 'i_lock'
                    break
        return None

    def outputs(self, ports):
        c = self.config
        outputs = {name: '0'*width for name, width in c.widths.items() if name.startswith('o_')}
        outputs['o_protocol_error'] = str(int(self.error and not (c.asynchronous and ports['i_rstb'] == '0')))
        if c.fixture:
            receiver = None if c.asynchronous and ports['i_rstb'] == '0' else self.receiver
            if receiver:
                outputs.update(o_received_valid='1', o_received_index=bits(receiver[0], c.index_width), o_received_payload=receiver[1])
        if ports['i_rstb'] == '0' or ports['i_flush'] == '1': return outputs
        active = self.active(ports)
        ones, unknowns = active.count('1'), active.count('x')
        outputs['o_contended'] = '1' if ones >= 2 else '0' if ones+unknowns <= 1 else 'x'
        outputs.update(o_pending=str(int(self.pending is not None)), o_locked=str(int(self.owner is not None)),
            o_lock_owner=bits(self.owner or 0, c.index_width))
        index, lock = self.selection(ports)
        if index == 'x':
            outputs.update(o_grant_valid='x', o_grant_index='x'*c.index_width, o_grant_onehot='x'*c.requesters,
                o_grant_lock='x' if c.has_lock else '0', o_grant_accepted='x' if ports['i_accept'] == '1' else '0')
        elif index is not None:
            outputs.update(o_grant_valid='1', o_grant_index=bits(index, c.index_width), o_grant_onehot=bits(1 << index, c.requesters),
                o_grant_lock=str(lock), o_grant_accepted=ports['i_accept'])
            if c.fixture: outputs['o_payload'] = payload(ports, index)
        return outputs

    def internals(self):
        c = self.config
        return dict(pointer=bits(self.order[0], c.index_width), pending_valid=str(int(self.pending is not None)),
            pending_index=bits(self.pending_index, c.index_width), pending_lock=str(self.pending_lock),
            locked=str(int(self.owner is not None)), lock_owner=bits(self.owner_storage, c.index_width), protocol_error=str(int(self.error)))

    def step(self, ports):
        c = self.config
        previous_class = self.state_class
        index, lock = self.selection(ports)
        errors = self.errors(ports)
        if ports['i_accept'] == '1' and index is None and not self.error: errors.add('invalid_accept')
        old_pointer, old_owner, was_pending = self.order[0], self.owner, self.pending is not None
        accepted = isinstance(index, int) and ports['i_accept'] == '1'
        if c.fixture:
            self.receiver = (index, payload(ports, index)) if accepted else None
        if errors:
            self.error = True
        elif not self.error:
            if accepted:
                next_index = (index+1) % c.requesters
                self.order = list(range(next_index, c.requesters)) + list(range(next_index))
                self.pending = None
                if c.has_lock:
                    self.owner = index if lock else None
                    self.owner_storage = index if lock else 0
            elif index is not None and not self.pending:
                self.pending = (index, lock)
                self.pending_index, self.pending_lock = index, lock
                if c.fixture: self.pending_payload = payload(ports, index)
        # Accepted-grant fairness pauses during lock, with no wall-clock bound.
        for requester in range(c.requesters):
            competing = self.active(ports)[requester] == '1' and not self.error
            if not competing: self.waits[requester] = 0
            elif old_owner is None and accepted:
                self.waits[requester] = 0 if index == requester else self.waits[requester]+1
                assert self.waits[requester] <= c.requesters-1, 'Accepted-grant fairness assertion failed'
        return dict(state=previous_class, pointer=old_pointer, owner=old_owner, pending=was_pending,
            winner=index, lock=lock, accepted=accepted, errors=errors)
