"""Cyclic order, legal backpressure/locks, hardware errors and random contention."""
from itertools import combinations, product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from round_robin_arbiter.config import LOCK_LENGTHS, LONG_STALL, PAYLOAD_WIDTH, STALL_LIMIT
from round_robin_arbiter.transaction import ArbiterItem


class ArbiterSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('round_robin_arbiter_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*config.widths[name] for name in config.inputs}
        self.pending = None
        self.last = None
        self.serial = 0

    def payloads(self):
        self.serial += 1
        return sum((((r << 26) | ((self.serial*131+r*17) & ((1 << 26)-1))) << (r*PAYLOAD_WIDTH)) for r in range(self.config.requesters))

    async def send(self, label, *, edge=True, random=False, pulse=False, **changes):
        c = self.config
        if c.fixture and 'i_payload' not in changes:
            packed = bits(self.payloads(), c.widths['i_payload'])
            if self.pending and changes.get('i_rstb', self.ports['i_rstb']) not in (0, '0') and changes.get('i_flush', self.ports['i_flush']) not in (1, '1'):
                index, _, word = self.pending
                start = len(packed)-(index+1)*PAYLOAD_WIDTH
                packed = packed[:start]+word+packed[start+PAYLOAD_WIDTH:]
            changes['i_payload'] = packed
        for name, value in changes.items(): self.ports[name] = bits(value, c.widths[name])
        item = ArbiterItem(label, self.ports, edge=edge, random=random, pulse=pulse)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.observation.ports
        if edge:
            if item.ports['i_rstb'] == '0' or item.ports['i_flush'] == '1': self.pending = None
            elif item.pre.ports['o_grant_accepted'] == '1': self.pending = None
            elif item.pre.ports['o_grant_valid'] == '1' and item.ports['i_accept'] == '0' and self.pending is None:
                index = int(item.pre.ports['o_grant_index'], 2)
                word = None
                if c.fixture:
                    packed = item.ports['i_payload']
                    word = packed[len(packed)-(index+1)*32:len(packed)-index*32]
                self.pending = index, int(item.pre.ports['o_grant_lock']), word
        return item

    async def clear(self, kind='flush', *, edge=True):
        await self.send(kind, edge=edge, i_rstb=int(kind != 'reset'), i_flush=int(kind == 'flush'),
            i_request=0, i_eligible=(1 << self.config.requesters)-1, i_lock=0, i_accept=0)
        await self.send('release_boundary', edge=False, i_rstb=1, i_flush=0)

    async def grant(self, index, *, accept=1, lock=0, edge=True):
        return await self.send('single_request', edge=edge, i_request=1 << index,
            i_eligible=(1 << self.config.requesters)-1, i_lock=(1 << index) if lock else 0, i_accept=accept)

    async def patterns(self):
        c, n = self.config, self.config.requesters
        full = (1 << n)-1
        await self.clear('reset')
        for pointer in range(n):
            await self.grant((pointer-1) % n)
            await self.send('no_request', edge=False, i_request=0, i_accept=0)
            for requester in range(n): await self.grant(requester, accept=0, edge=False)
        await self.clear()
        for a, b in combinations(range(n), 2):
            await self.send('request_pair', edge=False, i_request=(1 << a) | (1 << b), i_eligible=full, i_accept=0)
        for requests, eligible, maximal in product(range(n+1), range(n+1), (False, True)):
            eligibility = (1 << eligible)-1
            if not maximal: eligibility <<= n-eligible
            await self.send('population_cross', edge=False, i_request=(1 << requests)-1, i_eligible=eligibility, i_accept=0)
        if n <= 4:
            for pointer in range(n):
                await self.grant((pointer-1) % n)
                for requests, eligibility in product(range(1 << n), repeat=2):
                    await self.send('exhaustive_qualified_requests', edge=False, i_request=requests, i_eligible=eligibility, i_lock=0, i_accept=0)
        for a, b in product(range(n), repeat=2):
            await self.grant(a)
            await self.grant(b)
        await self.send('stream', i_request=full, i_eligible=full, i_lock=0, i_accept=1)
        for _ in range(max(16, 3*n)):
            await self.send('stream')

    async def backpressure(self):
        n = self.config.requesters
        full = (1 << n)-1
        for length in (*range(STALL_LIMIT+1), LONG_STALL):
            await self.clear()
            for _ in range(length): await self.grant(0, accept=0)
            await self.grant(0)
        for winner in range(n):
            await self.clear()
            await self.grant(winner, accept=0)
            for requests in (full, 1 << winner, full):
                await self.send('pending_other_changes', i_request=requests, i_eligible=full, i_lock=0, i_accept=0)
            await self.send('accept_pending', i_accept=1)

    async def locks(self):
        if not self.config.has_lock: return
        n = self.config.requesters
        full = (1 << n)-1
        for owner, length in product(range(n), LOCK_LENGTHS):
            await self.clear()
            await self.grant(owner, lock=1)
            for _ in range(2):
                await self.send('owner_gap', i_request=full ^ (1 << owner), i_eligible=full, i_lock=1 << owner, i_accept=0)
            for _ in range(length-1):
                await self.send('locked_beat', i_request=full, i_lock=1 << owner, i_accept=1)
            await self.send('final_owner_beat', i_request=full, i_lock=0, i_accept=1)
            await self.grant((owner+1) % n)
        for owner, following in product(range(n), repeat=2):
            await self.clear()
            await self.grant(owner, lock=1)
            await self.send('stalled_final_beat', i_request=full, i_eligible=full, i_lock=0, i_accept=0)
            await self.send('accept_final_beat', i_accept=1)
            await self.grant(following)

    async def state(self, name):
        await self.clear()
        if name in ('locked', 'locked_pending'):
            await self.grant(0, lock=1)
        if name in ('pending', 'locked_pending'):
            await self.grant(0, accept=0)
        if name == 'error':
            await self.send('empty_invalid_accept', i_request=0, i_accept=1)

    async def errors_and_boundaries(self):
        c, n = self.config, self.config.requesters
        classes = ('idle', 'pending', 'error') + (('locked', 'locked_pending') if c.has_lock else ())
        for boundary, state in product(('reset', 'flush'), classes):
            await self.state(state)
            await self.clear(boundary)
        for boundary in ('reset', 'flush'):
            await self.state('pending')
            # A pulse without a clock clamps outputs but only asynchronous
            # reset cancels ownership; restore the selected controls on release.
            await self.send('unclocked_boundary', edge=False, **{'i_rstb' if boundary == 'reset' else 'i_flush': 0 if boundary == 'reset' else 1})
            await self.send('release_unclocked_boundary', edge=False, i_rstb=1, i_flush=0)
            await self.clear()
        faults = ('pending_request', 'pending_eligibility') + (('pending_lock', 'owner_eligibility', 'owner_gap_release') if c.has_lock else ('lock_disabled',))
        for fault in faults:
            for requester in range(n):
                await self.clear()
                if fault.startswith('pending'):
                    await self.grant(requester, accept=0)
                    changes = dict(i_request=0) if fault == 'pending_request' else dict(i_eligible=((1 << n)-1) ^ (1 << requester)) if fault == 'pending_eligibility' else dict(i_lock=1 << requester)
                elif fault.startswith('owner'):
                    await self.grant(requester, lock=1)
                    changes = dict(i_eligible=((1 << n)-1) ^ (1 << requester)) if fault == 'owner_eligibility' else dict(i_request=0, i_lock=0)
                else:
                    changes = dict(i_request=1 << requester, i_lock=1 << requester)
                await self.send('sample_hardware_fault', i_accept=0, **changes)
                for _ in range(3):
                    await self.send('sticky_error_hold', i_request=(1 << n)-1, i_eligible=(1 << n)-1, i_lock=0, i_accept=1)
                await self.clear()

    async def ignored_unknowns(self):
        n = self.config.requesters
        full = (1 << n)-1
        for state in 'xz':
            await self.clear()
            await self.send('masked_request_unknown', edge=False, i_request=state*n, i_eligible=0, i_accept=0, i_lock=0)
            await self.send('masked_eligibility_unknown', edge=False, i_request=0, i_eligible=state*n)
            if self.config.has_lock:
                await self.send('unselected_lock_unknown', edge=False, i_request=0, i_eligible=full, i_lock=state*n)
                await self.grant(0, accept=0)
                if n > 1:
                    await self.send('pending_ignored_controls', edge=False, i_request=state*(n-1)+'1', i_eligible=state*(n-1)+'1', i_lock=state*(n-1)+'0')
                await self.clear()

    async def probe(self):
        c, n = self.config, self.config.requesters
        await self.clear('reset')
        name, state, position = c.probe.split(':')
        if name in ('pending_payload', 'payload_pulse'):
            await self.grant(0, accept=0)
            if name == 'payload_pulse': await self.send('illegal_payload_pulse', edge=False, pulse=True)
            else: await self.send('illegal_payload_change', edge=False, i_payload=int(self.ports['i_payload'], 2) ^ 1)
        elif name == 'accepted_payload':
            await self.send('unknown_accepted_payload', i_request=1, i_eligible=1, i_lock=0, i_accept=1, i_payload=state*(n*32))
        elif name.startswith(('pending_', 'owner_')):
            if name.startswith('owner_'): await self.grant(0, lock=1)
            else: await self.grant(0, accept=0)
            target = name.removeprefix('pending_').removeprefix('owner_')
            word = list(self.ports[target]); word[-1] = state
            await self.send('unknown_pending_control', **{target: ''.join(word)})
        else:
            changes = dict(i_request=0, i_eligible=(1 << n)-1, i_lock=0, i_accept=0)
            if name in ('i_request', 'i_eligible', 'i_lock'):
                index = int(position)
                await self.grant((index-1) % n)
                changes['i_request'] = 1 << index if name != 'i_request' else 0
                word = list(bits(changes[name], n)); word[-index-1] = state
                changes[name] = ''.join(word)
            else: changes[name] = state
            await self.send('unknown_control', **changes)
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.patterns()
        await self.backpressure()
        await self.locks()
        await self.errors_and_boundaries()
        await self.ignored_unknowns()
        c, n = self.config, self.config.requesters
        for index in range(c.random_cycles):
            request, eligible = self.rng.getrandbits(n), self.rng.getrandbits(n)
            lock = self.rng.getrandbits(n) if c.has_lock else 0
            if self.last['o_locked'] == '1':
                owner = int(self.last['o_lock_owner'], 2)
                eligible |= 1 << owner
                if not request & (1 << owner): lock |= 1 << owner
            if self.pending:
                owner, held_lock, _ = self.pending
                request |= 1 << owner; eligible |= 1 << owner
                lock = (lock & ~(1 << owner)) | (held_lock << owner)
            valid = bool(request & eligible)
            if self.last['o_locked'] == '1':
                valid = bool(request & (1 << int(self.last['o_lock_owner'], 2)))
            await self.send(f'random_{index}', random=True, i_rstb=int(self.rng.random() >= 0.02), i_flush=int(self.rng.random() < 0.03),
                i_request=request, i_eligible=eligible, i_lock=lock, i_accept=int(valid and self.rng.random() < 0.7))
        await self.clear()
