"""Persistent client streams, adverse bank timing, and coordinated recovery."""
import random
from pyuvm import uvm_sequence
from scratchpad_controller.model import mapping, number, pack, unpack
from scratchpad_controller.transaction import ControllerItem


class ControllerSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('scratchpad_controller_sequence')
        self.c = c
        self.rng = random.Random(c.seed)
        self.clients = [None] * c.NUM_CLIENTS
        self.controls = dict(i_rstb=1, i_flush=0, i_error_clear=0, i_perm_valid=0,
            i_read_permission=0, i_write_permission=0, i_client_rsp_ready=(1 << c.NUM_CLIENTS) - 1)
        self.last = None
        self.full_permissions = (1 << (c.NUM_CLIENTS * c.NUM_BANKS)) - 1

    def request(self, address=0, write=False, size=None, strobe=None, data=None, tag=3):
        c = self.c
        size = c.bytes.bit_length() - 1 if size is None else size
        return dict(address=address, write=int(write), size_log2=size,
            wstrobe=(1 << (1 << size)) - 1 if strobe is None else strobe,
            wdata=self.rng.getrandbits(c.DATA_WIDTH) if data is None else data, tag=tag % (1 << c.CLIENT_TAG_WIDTH))

    def address(self, bank, word=0):
        # Invert only by searching legal word addresses; avoids sharing mapper
        # implementation with the test's directed address selection.
        return next(a for a in range(0, self.c.capacity, self.c.bytes)
                    if mapping(self.c, a) == (bank, word * self.c.bytes))

    async def tick(self, label='cycle', *, peer=None, edge=True, random=False, **controls):
        item = ControllerItem(label, [None if e is None else e.copy() for e in self.clients],
                              self.controls | controls, peer=peer, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        if number(item.pre.ports['i_rstb']) == 0 and (edge or self.c.ASYNC_RESET) or (
                edge and number(item.pre.ports['o_flushing']) == 1):
            self.clients = [None] * self.c.NUM_CLIENTS
        elif edge:
            for n, bit in enumerate(unpack(item.pre.ports['o_client_req_ready'], self.c.NUM_CLIENTS, 1)):
                if bit == 1:
                    self.clients[n] = None
        self.last = item.post.ports
        return item

    async def send(self, req, client=0, **options):
        assert self.clients[client] is None
        self.clients[client] = req
        for _ in range(500):
            item = await self.tick('request', **options)
            if self.clients[client] is None:
                return item
        raise AssertionError('Continuously ready bank failed to serve client')

    async def drain(self):
        for _ in range(1000):
            await self.tick('drain')
            if not number(self.last['o_busy']) and all(e is None for e in self.clients):
                return
        raise AssertionError('Fair clients and banks failed to drain')

    async def transaction(self, req, client=0):
        item = await self.send(req, client)
        await self.drain()
        return item

    async def reset(self):
        await self.tick('reset_without_clock', edge=False, i_rstb=0)
        await self.tick('reset_edge', i_rstb=0)
        await self.tick('reset_release')

    async def flush(self):
        await self.tick('flush_without_clock', edge=False, i_flush=1)
        await self.tick('flush_start', i_flush=1)
        for _ in range(40):
            if number(self.last['o_flush_completed']):
                break
            await self.tick('flush_wait', i_flush=1)
        else:
            raise AssertionError('Banks failed to acknowledge coordinated flush')
        for _ in range(3):
            await self.tick('held_flush', i_flush=1)
            assert number(self.last['o_flush_completed']) == 0
        await self.tick('flush_release')
        await self.tick('clear_error', i_error_clear=1)
        assert number(self.last['o_error']) == 0

    async def permissions(self, read=None, write=None):
        await self.drain()
        await self.tick('permission_update', i_perm_valid=1,
            i_read_permission=self.full_permissions if read is None else read,
            i_write_permission=self.full_permissions if write is None else write)
        assert number(self.last['o_permission_updated']) == int(bool(self.c.ENFORCE_PERMISSIONS))
        await self.tick('permission_event_clear')

    async def initialize(self):
        # All real bank bytes are initialized through accepted public writes.
        if self.c.integration:
            for address in range(0, self.c.capacity, self.c.bytes):
                await self.send(self.request(address, True), client=(address // self.c.bytes) % self.c.NUM_CLIENTS)
            await self.drain()

    async def address_campaign(self):
        c = self.c
        addresses = range(c.capacity) if not c.integration and c.capacity <= 2048 else range(0, c.capacity, max(c.bytes, c.capacity // 64 // c.bytes * c.bytes))
        for address in addresses:
            await self.send(self.request(address, size=0), client=address % c.NUM_CLIENTS)
        await self.drain()
        for n in range(c.NUM_CLIENTS):
            for b in range(c.NUM_BANKS):
                await self.send(self.request(self.address(b), True), n)
                await self.send(self.request(self.address(b)), n)
        await self.drain()
        for size in range(c.bytes.bit_length()):
            for offset in range(0, c.bytes, 1 << size):
                for mask in {0, 1, (1 << (1 << size)) - 1, sum(1 << n for n in range(0, 1 << size, 2))}:
                    await self.send(self.request(offset, True, size, mask))
                    await self.send(self.request(offset, False, size))
        await self.drain()
        for state in 'xz':
            await self.transaction(self.request(write=True, size=0, strobe=1,
                data=state * (c.DATA_WIDTH - 8) + '10110101'))
            req = self.request()
            req.update(wdata=state * c.DATA_WIDTH, wstrobe=state * c.bytes)
            await self.transaction(req)

    async def arbitration(self):
        c = self.c
        # Sweep contender populations at every bank. Later arrivals must not
        # displace its registered winner; subsequent services rotate fairly.
        for bank in range(c.NUM_BANKS):
            self.clients[0] = self.request(self.address(bank), write=True)
            await self.tick('grant_pending', peer=dict(ready=0), i_client_rsp_ready=0)
            for n in range(1, c.NUM_CLIENTS):
                self.clients[n] = self.request(self.address(bank), write=bool(n % 2))
                await self.tick('new_contender', peer=dict(ready=0), i_client_rsp_ready=0)
            for _ in range(2):
                await self.tick('all_contenders', peer=dict(ready=0), i_client_rsp_ready=0,
                                i_perm_valid=1, i_read_permission=0, i_write_permission=0)
                assert number(self.last['o_perm_ready']) == 0
            await self.drain()
            self.clients = [self.request(self.address(bank), write=bool(n % 2))
                            for n in range(c.NUM_CLIENTS)]
            await self.drain()
        for _ in range(3 * c.NUM_CLIENTS):
            for n in range(c.NUM_CLIENTS):
                if self.clients[n] is None:
                    self.clients[n] = self.request(self.address(n % c.NUM_BANKS), bool(n % 2))
            await self.tick('parallel_clients')
        await self.drain()
        for _ in range(c.MAX_OUTSTANDING_PER_CLIENT):
            await self.send(self.request(write=True), i_client_rsp_ready=0)
        self.clients[0] = self.request()
        for _ in range(8):
            await self.tick('client_full', i_client_rsp_ready=0)
        await self.drain()
        if c.NUM_BANKS > 1 and c.MAX_OUTSTANDING_PER_CLIENT > 1 and not c.integration:
            for mode in ('reverse', 'simultaneous'):
                await self.send(self.request(self.address(0)), peer=dict(launch=0), i_client_rsp_ready=0)
                await self.send(self.request(self.address(1)), peer=dict(launch=0), i_client_rsp_ready=0)
                for _ in range(12):
                    await self.tick('hold_bank_results', peer=dict(launch=0), i_client_rsp_ready=0)
                if mode == 'reverse':
                    for _ in range(3):
                        await self.tick('younger_before_older', peer=dict(launch=2), i_client_rsp_ready=0)
                await self.drain()

    async def illegal(self):
        c = self.c
        changes = []
        if c.capacity < 1 << c.aliases['A']:
            changes.append(dict(address=c.capacity))
        if c.bytes.bit_length() - 1 < (1 << c.aliases['S']) - 1:
            changes.append(dict(size_log2=c.bytes.bit_length()))
        if c.bytes > 1:
            changes.extend((dict(address=c.bytes - 1, size_log2=1), dict(size_log2=0, wstrobe=2)))
        if c.bytes >= 4:
            changes.append(dict(address=1, size_log2=1))
        widths = dict(write=1, address=c.aliases['A'], size_log2=c.aliases['S'], tag=c.CLIENT_TAG_WIDTH,
                      wstrobe=c.bytes)
        for n in range(c.NUM_CLIENTS):
            for change in changes:
                await self.transaction(self.request(write=True) | change, n)
            for field, width in widths.items():
                for state in 'xz':
                    await self.transaction(self.request(write=True) | {field: state * width}, n)
        if not c.integration:
            for state in 'xz':
                self.clients[0] = self.request(write=True)
                await self.tick('unknown_bank_ready', peer=dict(ports=dict(i_bank_req_ready=state * c.NUM_BANKS)))
                await self.drain()
                await self.send(self.request(write=True), i_client_rsp_ready=0)
                for _ in range(12):
                    await self.tick('unknown_client_ready', i_client_rsp_ready=state * c.NUM_CLIENTS)
                await self.drain()

    async def permission_campaign(self):
        c = self.c
        if not c.ENFORCE_PERMISSIONS:
            await self.permissions(0, 0)
            return
        for read, write in ((0, self.full_permissions), (self.full_permissions, 0),
                (sum(1 << (n * c.NUM_BANKS + b) for n in range(c.NUM_CLIENTS)
                     for b in range(c.NUM_BANKS) if (n + b) % 2 == 0), self.full_permissions)):
            await self.permissions(read, write)
            for n in range(c.NUM_CLIENTS):
                for b in range(c.NUM_BANKS):
                    for op in (False, True):
                        await self.send(self.request(self.address(b), op), n)
            await self.drain()
        await self.permissions('x' * (c.NUM_CLIENTS * c.NUM_BANKS), 'z' * (c.NUM_CLIENTS * c.NUM_BANKS))
        for n in range(c.NUM_CLIENTS):
            await self.transaction(self.request(), n)
        await self.permissions()

    async def reliability(self):
        if self.c.integration:
            if not self.c.protection:
                return
            for b in range(self.c.NUM_BANKS):
                for n in range(self.c.NUM_CLIENTS):
                    address = self.address(b)
                    await self.transaction(self.request(address, True), n)
                    await self.tick('single_storage_fault', peer=dict(fault=(b, 0, 1)))
                    await self.transaction(self.request(address), n)
                    await self.transaction(self.request(address, True), n)
                    mask = 3 if self.c.protection == 2 else 1 << self.c.DATA_WIDTH
                    await self.tick('uncorrectable_storage_fault', peer=dict(fault=(b, 0, mask)))
                    await self.transaction(self.request(address), n)
                    await self.transaction(self.request(address, True), n)
            return
        for b in range(self.c.NUM_BANKS):
            for n in range(self.c.NUM_CLIENTS):
                for code, corrected in [(0, 1), *((code, 0) for code in range(10))]:
                    await self.send(self.request(self.address(b)), n, peer=dict(status={b: dict(
                        error=int(code != 0), error_code=code, corrected=corrected,
                        uncorrectable=int(code in (7, 8))) }))
            await self.drain()

    async def malformed(self):
        c = self.c
        if c.integration:
            return
        cases = ['unknown_tag', 'unallocated', 'duplicate', 'operation', 'status', 'unknown_status']
        if c.NUM_BANKS > 1:
            cases.append('bank')
        if c.NUM_CLIENTS < 1 << max(1, (c.NUM_CLIENTS - 1).bit_length()):
            cases.append('client')
        if c.MAX_OUTSTANDING_PER_CLIENT < 1 << c.slot_width:
            cases.append('slot')
        for case in cases:
            await self.drain()
            item = await self.send(self.request(self.address(0)), peer=dict(launch=0), i_client_rsp_ready=0)
            tag = unpack(item.pre.ports['o_bank_req_tag'], c.NUM_BANKS, c.aliases['K'])[0]
            b = 1 if case == 'bank' else 0
            changes = dict(tag=tag)
            if case == 'unknown_tag':
                changes['tag'] = 'x' * c.aliases['K']
            elif case == 'client':
                changes['tag'] = c.NUM_CLIENTS << c.slot_width
            elif case == 'slot':
                changes['tag'] = c.MAX_OUTSTANDING_PER_CLIENT
            elif case == 'unallocated':
                await self.flush()
            elif case == 'operation':
                changes['write'] = 1
            elif case == 'status':
                changes.update(error=1, error_code=8, corrected=1, uncorrectable=1)
            elif case == 'unknown_status':
                changes['error_code'] = 'z' * 4
            elif case == 'duplicate':
                await self.tick('first_completion', peer=dict(launch=0, inject=(b, changes)), i_client_rsp_ready=0)
            await self.tick('malformed_' + case, peer=dict(launch=0, inject=(b, changes)), i_client_rsp_ready=0)
            assert number(self.last['o_error']) == 1
            old_error = self.last['o_error_code']
            await self.tick('sticky_first_error', peer=dict(launch=0, inject=(0, dict(tag='z' * c.aliases['K']))),
                            i_client_rsp_ready=0, i_error_clear=1)
            assert self.last['o_error_code'] == old_error
            await self.flush()

    async def counter_campaign(self):
        if not self.c.instrumentation:
            return
        for _ in range(260):
            await self.send(self.request() | dict(tag='x' * self.c.CLIENT_TAG_WIDTH))
        await self.drain()
        for _ in range(4):
            await self.tick('disabled_counter_clear', peer=dict(counter_enable=0, counter_clear=1))
        await self.tick('enabled_counter_clear', peer=dict(counter_clear=1))

    async def random_campaign(self):
        c = self.c
        permission_pending = False
        read_permissions = write_permissions = self.full_permissions
        for cycle in range(c.random_cycles):
            if cycle % 97 == 0 and not permission_pending:
                permission_pending = bool(c.ENFORCE_PERMISSIONS)
                read_permissions = self.rng.getrandbits(c.NUM_CLIENTS * c.NUM_BANKS)
                write_permissions = self.rng.getrandbits(c.NUM_CLIENTS * c.NUM_BANKS)
            for n in range(c.NUM_CLIENTS):
                if self.clients[n] is None and self.rng.randrange(4):
                    size = self.rng.randrange(c.bytes.bit_length())
                    address = self.rng.randrange(c.capacity // (1 << size)) * (1 << size)
                    self.clients[n] = self.request(address, bool(self.rng.getrandbits(1)), size,
                        self.rng.getrandbits(1 << size), tag=self.rng.randrange(4))
                    if self.rng.randrange(35) == 0:
                        self.clients[n]['size_log2'] = (1 << c.aliases['S']) - 1
            status = {}
            if not c.integration:
                for b in range(c.NUM_BANKS):
                    if self.rng.randrange(16) == 0:
                        code = self.rng.choice((0, 7, 8))
                        status[b] = dict(error=int(code != 0), error_code=code,
                                         corrected=int(code == 0), uncorrectable=int(code != 0))
            await self.tick('random', random=True, peer=dict(ready=self.rng.getrandbits(c.NUM_BANKS),
                launch=self.rng.getrandbits(c.NUM_BANKS), status=status),
                i_client_rsp_ready=self.rng.getrandbits(c.NUM_CLIENTS),
                i_flush=int(cycle % 211 == 210), i_perm_valid=int(permission_pending),
                i_read_permission=read_permissions, i_write_permission=write_permissions)
            if number(self.last['o_permission_updated']):
                permission_pending = False
        await self.drain()

    async def body(self):
        c = self.c
        await self.reset()
        if c.ENFORCE_PERMISSIONS:
            await self.transaction(self.request(write=True))
        await self.permissions()
        await self.initialize()
        if c.probe:
            state = c.probe[-1]
            if c.probe.startswith('write'):
                await self.transaction(self.request(write=True, data=state * c.DATA_WIDTH))
            else:
                item = await self.send(self.request(), peer=dict(launch=0), i_client_rsp_ready=0)
                tag = unpack(item.pre.ports['o_bank_req_tag'], c.NUM_BANKS, c.aliases['K'])[0]
                await self.tick('unknown_read_probe', peer=dict(launch=0, inject=(0, dict(tag=tag, rdata=state * c.DATA_WIDTH))))
            raise AssertionError('Required data assertion did not fire')
        await self.address_campaign()
        await self.arbitration()
        await self.illegal()
        await self.permission_campaign()
        await self.reliability()
        await self.malformed()
        await self.counter_campaign()
        await self.flush()
        self.clients = [self.request(self.address(n % c.NUM_BANKS), True) for n in range(c.NUM_CLIENTS)]
        await self.tick('flush_pending_grant', peer=dict(ready=0), i_client_rsp_ready=0)
        await self.flush()
        await self.send(self.request(write=True), i_client_rsp_ready=0)
        for _ in range(12):
            await self.tick('hold_response_for_reset', i_client_rsp_ready=0)
        await self.reset()
        await self.permissions()
        await self.random_campaign()
        await self.flush()
        await self.permissions()
        await self.transaction(self.request())
        await self.drain()
