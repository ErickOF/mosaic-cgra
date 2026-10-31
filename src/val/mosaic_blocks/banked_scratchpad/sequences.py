"""Directed contract checks and seeded multi-client traffic through public ports."""
import random
from pyuvm import uvm_sequence
from banked_scratchpad.model import lane, number, map_address
from banked_scratchpad.transaction import ScratchpadItem, INPUTS


class ScratchpadSequence(uvm_sequence):
    def __init__(self, c, active, coverage):
        super().__init__('specification_sequence')
        self.c, self.a, self.active, self.coverage = c, c.a, active, coverage
        self.base = {n: 0 for n in INPUTS}
        self.base.update(i_enable=1, i_client_rsp_ready=(1 << c.NUM_CLIENTS) - 1,
            i_region_rsp_ready=1, i_event_ready=1, i_bank_power_ack=(1 << c.NUM_BANKS) - 1)
        self.index = self.tag = 0
        self.responses = {}
        self.last = {}
        self.rng = random.Random(c.seed)

    async def cycle(self, label='idle', fault=None, edge=True, **ports):
        self.index += 1
        item = ScratchpadItem(f'{label}_{self.index}', self.base | ports, fault, edge)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = {n: number(v) for n, v in item.post.items()}
        if item.pre:
            p = item.pre
            for client in range(self.a['C']):
                if p['o_client_rsp_valid'] >> client & p['i_client_rsp_ready'] >> client & 1:
                    tag = lane(p['o_client_rsp_tag'], self.a['T'], client)
                    self.responses[client, tag] = p
        return item

    async def idle(self, cycles=3, **ports):
        for _ in range(cycles):
            await self.cycle(**ports)

    async def reset(self):
        await self.idle(2, i_reset_n=0)
        self.base['i_reset_n'] = 1
        await self.idle(4)
        self.responses.clear()
        self.coverage.hit('reset')

    async def drain(self):
        for _ in range(5000):
            item = await self.cycle(i_drain=1)
            if item.pre['o_drained']:
                self.coverage.hit('drain')
                return
        raise AssertionError('Drain timed out')

    async def command(self, op, r=0, s=0, stall=0, **changes):
        model = self.active['model']
        da = model.regions[r] if r < self.a['R'] else {}
        db = model.regions[s] if s < self.a['R'] else {}
        settings = dict(cmd_opcode=op, cmd_a=r, cmd_b=s,
            expected_generation_a=da.get('generation', 0), expected_generation_b=db.get('generation', 0),
            expected_state_a=da.get('state', 0), expected_state_b=db.get('state', 0),
            base=da.get('base', 0), limit=da.get('limit', 0), owner_id=da.get('owner', 5),
            kernel_id=da.get('kernel', 3), state=da.get('state', 5),
            contents_valid=da.get('contents', 0), read_mask=da.get('read_mask', (1 << self.a['C']) - 1),
            write_mask=da.get('write_mask', (1 << self.a['C']) - 1),
            buffer_group=da.get('group_id', 0), buffer_role=da.get('role', 0)) | changes
        driven = {'i_region_' + n: v for n, v in settings.items()}
        for _ in range(5000):
            item = await self.cycle('command', i_region_cmd_valid=1, **driven)
            if item.pre['o_region_cmd_ready']:
                break
        else:
            raise AssertionError('Region command admission timed out')
        for _ in range(stall):
            await self.cycle(i_region_rsp_ready=0, i_event_ready=0)
        for _ in range(5000):
            item = await self.cycle('command_result')
            if item.pre['o_region_rsp_valid']:
                return item.pre
        raise AssertionError('Region response timed out')

    def request(self, addr=0, *, opcode=0, size=None, data=0, region=None, **changes):
        if size is None:
            size = self.a['Y']
        if region is None:
            matches = [r for r, d in enumerate(self.active['model'].regions)
                if d['valid'] and d['base'] <= addr < d['limit']]
            region = matches[0] if matches else 0
        d = self.active['model'].regions[region]
        self.tag = (self.tag + 1) % (1 << self.a['T'])
        return dict(opcode=opcode, addr=addr, size=size, wdata=data,
            wstrb=(((1 << size) - 1) << (addr % self.a['Y'])) & ((1 << self.a['Y']) - 1), owner_id=d['owner'],
            kernel_id=d['kernel'], region_id=region, generation=d['generation'], tag=self.tag) | changes

    def ports(self, requests):
        widths = dict(opcode=2, addr=self.a['A'], size=self.a['Z'], wdata=self.a['D'],
            wstrb=self.a['Y'], owner_id=self.a['O'], kernel_id=self.a['K'],
            region_id=self.a['RI'], generation=self.a['G'], tag=self.a['T'])
        values = dict(i_client_req_valid=sum(1 << c for c in requests))
        for n, w in widths.items():
            values['i_client_req_' + n] = sum((x[n] & ((1 << w) - 1)) << (c * w) for c, x in requests.items())
        return values

    async def send(self, x, c=0, wait=True, **ports):
        self.responses.pop((c, x['tag']), None)
        for _ in range(5000):
            item = await self.cycle('request', **(self.ports({c: x}) | ports))
            if item.pre['o_client_req_ready'] >> c & 1:
                break
        else:
            raise AssertionError('Request admission timed out')
        if wait:
            return await self.response(c, x['tag'])
        return x['tag']

    async def response(self, c, tag):
        for _ in range(5000):
            if (c, tag) in self.responses:
                return self.responses.pop((c, tag))
            await self.cycle('wait_response')
        raise AssertionError(('Response timed out', c, tag, self.last))

    async def setup(self):
        await self.reset()
        a, c = self.a, self.c
        # Only explicitly initialized words are later read. Publishing a region
        # never claims that reset initialized untouched macro locations.
        boundary = a['capacity'] // 2 // c.INTERLEAVE_BYTES * c.INTERLEAVE_BYTES
        ranges = [(0, a['capacity'])] if a['R'] == 1 else [(0, boundary), (a['capacity'] - boundary, a['capacity'])]
        for r, (base, limit) in enumerate(ranges):
            rsp = await self.command(1, r, base=base, limit=limit, owner_id=5, kernel_id=3,
                state=5, contents_valid=0, read_mask=(1 << a['C']) - 1,
                write_mask=(1 << a['C']) - 1,
                buffer_group=1 if c.SUPPORT_DOUBLE_BUFFER and len(ranges) == 2 else 0,
                buffer_role=(1 if r == 0 else 2) if c.SUPPORT_DOUBLE_BUFFER and len(ranges) == 2 else 0)
            assert not rsp['o_region_rsp_error']
        if c.ENFORCE_REGIONS:
            rsp = await self.send(self.request())
            assert lane(rsp['o_client_rsp_error_code'], 8, 0) == 15
            self.coverage.hit('invalid_contents')
        self.words = sorted({0, a['capacity'] - a['Y'],
            *(base for base, _ in ranges),
            *(min(b * c.INTERLEAVE_BYTES, a['capacity'] - a['Y']) for b in range(a['B'])),
            *(min(base + b * c.INTERLEAVE_BYTES, limit - a['Y'])
                for base, limit in ranges for b in range(a['B']))})
        for addr in self.words:
            await self.send(self.request(addr, opcode=1, data=self.rng.getrandbits(a['D'])))
        for r in range(len(ranges)):
            await self.command(2, r, contents_valid=1)
        await self.idle(3)

    async def directed(self):
        a, c, cov = self.a, self.c, self.coverage
        for size in (1 << i for i in range(a['Y'].bit_length())):
            for offset in range(0, a['Y'], size):
                await self.send(self.request(offset, opcode=1, size=size,
                    data=self.rng.getrandbits(8 * size)))
                await self.send(self.request(offset, size=size))
        for addr in self.words:
            await self.send(self.request(addr))
        cov.hit('all_sizes_positions')
        cov.hit('bank_region_boundaries')
        for changes in (dict(size=0), dict(size=min(3, a['Y'] + 1)), dict(opcode=3),
            dict(addr=1 if a['Y'] > 1 else 0, size=a['Y'] if a['Y'] > 1 else 0), dict(opcode=1, wstrb=0),
            dict(opcode=1, wstrb=((1 << a['Y']) - 1) ^ 1)):
            await self.send(self.request(**changes))
        if a['Y'] >= 4:
            await self.send(self.request(1, size=2))
        if a['capacity'] & (a['capacity'] - 1):
            await self.send(self.request(a['capacity']))
        if c.ENFORCE_REGIONS:
            for changes in (dict(generation=0), dict(owner_id=4), dict(kernel_id=2)):
                await self.send(self.request(**changes))
            if a['R'] > 1:
                await self.send(self.request(region=1))
            await self.command(2, state=4, write_mask=(1 << a['C']) - 1)
            for client in range(a['C']):
                await self.send(self.request(owner_id=1, kernel_id=1), client)
                await self.send(self.request(opcode=1), client)
            await self.command(2, state=1, contents_valid=1)
            if a['C'] > 1:
                await self.send(self.request(), 1)
            await self.command(2, state=5, read_mask=0)
            await self.send(self.request())
            await self.command(2, state=5, read_mask=(1 << a['C']) - 1)
            cov.hit('ownership_permissions')
        for changes in (dict(expected_generation_a=0), dict(expected_state_a=0)):
            rsp = await self.command(2, **changes)
            assert rsp['o_region_rsp_error']
        await self.command(0, stall=6)
        await self.command(1, base=0, limit=c.INTERLEAVE_BYTES)
        if a['R'] > 2:
            await self.command(1, 2, base=0, limit=c.INTERLEAVE_BYTES)
            await self.command(1, 2, base=1, limit=c.INTERLEAVE_BYTES)
        cov.hit('management_compare_and_stall')
        if a['R'] > 1:
            if c.SUPPORT_DOUBLE_BUFFER:
                await self.command(2, 1, contents_valid=0)
                rsp = await self.command(3, 0, 1)
                assert rsp['o_region_rsp_error_code'] == 10
                await self.command(2, 1, contents_valid=1)
                rsp = await self.command(3, 0, 1, stall=5)
                assert not rsp['o_region_rsp_error']
                await self.send(self.request(0))
                await self.send(self.request(self.active['model'].regions[1]['base']))
                cov.hit('atomic_swap')
            else:
                rsp = await self.command(3, 0, 1)
                assert rsp['o_region_rsp_error']
                cov.hit('swap_disabled')
        # Fill each completion position while holding responses, then release.
        count = c.MAX_OUTSTANDING_PER_CLIENT
        tags = []
        for _ in range(count):
            x = self.request(0)
            tags.append(await self.send(x, wait=False, i_client_rsp_ready=0))
        await self.idle(12, i_client_rsp_ready=0)
        assert lane(self.last['o_client_outstanding'], a['CO'], 0) == count
        await self.idle(2, i_client_rsp_ready=0, i_enable=0)
        for tag in tags:
            await self.response(0, tag)
        cov.hit('full_occupancy_backpressure')
        # Fence both empty and behind earlier writes; unrelated clients progress.
        await self.send(self.request(opcode=2))
        if count > 1:
            await self.send(self.request(opcode=1, data=123), wait=False, i_client_rsp_ready=0)
            tag = await self.send(self.request(opcode=2), wait=False, i_client_rsp_ready=0)
            await self.idle(18, i_client_rsp_ready=0)
            await self.response(0, tag)
        cov.hit('fence')
        await self.drain()

    async def traffic(self):
        p, a, cov = self.c, self.a, self.coverage
        pending = {}
        # Persistent requests obey ready/valid stability; shared bank contention
        # and independent banks alternate with seeded data, sizes and stalls.
        for tick in range(p.random_cycles):
            for client in range(a['C']):
                if client not in pending and self.rng.randrange(4):
                    addr = self.words[self.rng.randrange(len(self.words))]
                    if tick % 80 < 20:
                        addr = 0
                    size = 1 << self.rng.randrange(a['Y'].bit_length())
                    addr += self.rng.randrange(a['Y'] // size) * size
                    x = self.request(addr, opcode=self.rng.randrange(2), size=size,
                        data=self.rng.getrandbits(8 * size))
                    # Inject local errors among legal, competing operations.
                    if self.rng.randrange(12) == 0:
                        x['wstrb'] = 0
                        x['opcode'] = 1
                    pending[client] = x
            ready = self.rng.getrandbits(a['C']) if tick % 53 < 12 else (1 << a['C']) - 1
            item = await self.cycle('random', **self.ports(pending), i_client_rsp_ready=ready)
            for client in list(pending):
                if item.pre['o_client_req_ready'] >> client & 1:
                    del pending[client]
            cov.counts['random_cycles'] += 1
        while pending:
            item = await self.cycle(**self.ports(pending))
            for client in list(pending):
                if item.pre['o_client_req_ready'] >> client & 1:
                    del pending[client]
        await self.drain()
        cov.hit('random_multi_client')

    async def unknown_controls(self):
        # Four-state probes reject unknown legality inputs without poisoning any
        # protected record. Inactive read payload bits do not affect legality.
        c = 0
        for field in ('addr', 'size', 'owner_id', 'kernel_id', 'wstrb'):
            x = self.request(opcode=1 if field == 'wstrb' else 0)
            ports = self.ports({c: x})
            name = 'i_client_req_' + field
            ports[name] = 'x' * self.c.widths[name]
            item = await self.cycle('unknown_' + field, **ports)
            assert item.pre['o_client_req_ready'] & 1
            rsp = await self.response(c, x['tag'])
            assert lane(rsp['o_client_rsp_error_code'], 8, c) == 1
            assert not rsp['o_error']
        x = self.request()
        ports = self.ports({0: x})
        ports['i_client_req_wdata'] = 'x' * self.c.widths['i_client_req_wdata']
        ports['i_client_req_wstrb'] = 'x' * self.c.widths['i_client_req_wstrb']
        item = await self.cycle('inactive_read_payload', **ports)
        assert item.pre['o_client_req_ready'] & 1
        await self.response(0, x['tag'])
        self.coverage.hit('unknown_control_containment')

    async def generation_wrap(self):
        maximum = (1 << self.a['G']) - 1
        while self.active['model'].regions[0]['generation'] < maximum:
            await self.command(2, contents_valid=1)
        rsp = await self.command(2, contents_valid=1)
        assert rsp['o_region_rsp_error_code'] == 8
        await self.command(4)
        rsp = await self.command(1, base=0, limit=self.a['capacity'] // 2,
            contents_valid=1, state=5, read_mask=(1 << self.a['C']) - 1,
            write_mask=(1 << self.a['C']) - 1)
        assert not rsp['o_region_rsp_error']
        assert self.active['model'].regions[0]['generation'] == 1
        await self.send(self.request())
        self.coverage.hit('generation_wrap_refusal_reprovision')

    async def faults(self):
        c, a, cov = self.c, self.a, self.coverage
        # Full overwrite establishes a valid codeword for every fault experiment.
        for mask in (1, 3) if c.PROTECTION_MODE == 2 else (1,):
            await self.send(self.request(opcode=1, data=0xA5))
            await self.cycle('storage_fault', fault=('memory', (0, 0), mask))
            await self.send(self.request())
            if c.PROTECTION_MODE:
                await self.send(self.request(opcode=1, size=1, data=0x39))
            await self.send(self.request(opcode=1, data=0xA5))
        cov.hit('storage_faults')
        if c.CONTROL_PROTECTION:
            self.active['allow_error'] = True
            await self.cycle('descriptor_fault', fault=('descriptor', 0,
                1 if c.CONTROL_PROTECTION == 1 else 3))
            assert self.last['o_error'] and not self.last['o_client_req_ready']
            await self.cycle(fault=('release', 0, 0))
            await self.idle(3, i_error_clear=1)
            assert not self.last['o_error']
            self.active['allow_error'] = False
            cov.hit('control_fault')

    async def flush(self):
        # A completed write is irrevocable even if its response is canceled.
        await self.send(self.request(opcode=1, data=0x71), wait=False, i_client_rsp_ready=0)
        await self.idle(25, i_client_rsp_ready=0)
        assert self.last['o_client_rsp_valid'] & 1
        for _ in range(100):
            item = await self.cycle('flush', i_flush=1)
            if item.post['o_flush_completed']:
                break
        else:
            raise AssertionError('Flush timed out')
        await self.idle(5)
        await self.send(self.request())
        self.coverage.hit('flush_preserves_storage')

    async def recovery(self):
        # Cancel reads at different admission/backend/response positions. All
        # surviving data was committed before cancellation began.
        for delay in (0, 1, self.c.BACKEND_READ_LATENCY + 2):
            await self.send(self.request(), wait=False, i_client_rsp_ready=0)
            await self.idle(delay, i_client_rsp_ready=0)
            for _ in range(100):
                await self.cycle('pipeline_flush', i_flush=1)
                if self.last['o_flush_completed']:
                    break
            else:
                raise AssertionError('Pipeline flush timed out')
            await self.idle(4)
            await self.send(self.request())
        self.coverage.hit('pipeline_flush')
        # Reset cancels protocol state and descriptors without erasing SRAM.
        saved = [d.copy() for d in self.active['model'].regions]
        await self.send(self.request(), wait=False, i_client_rsp_ready=0)
        await self.reset()
        for r, d in enumerate(saved):
            if d['valid']:
                await self.command(1, r, base=d['base'], limit=d['limit'],
                    owner_id=d['owner'], kernel_id=d['kernel'], state=d['state'],
                    contents_valid=d['contents'], read_mask=d['read_mask'],
                    write_mask=d['write_mask'], buffer_group=d['group_id'], buffer_role=d['role'])
        await self.send(self.request())
        self.coverage.hit('reset_preserves_storage')

    async def stale_completion(self):
        self.active['allow_error'] = True
        await self.send(self.request(), wait=False, i_client_rsp_ready=0)
        for _ in range(100):
            if self.active.get('completion_pending', 0) & 1:
                break
            await self.cycle('wait_internal_completion', i_client_rsp_ready=0)
        else:
            raise AssertionError('No internal completion to corrupt')
        await self.cycle('stale_internal_epoch', fault=('completion', 0, 1), i_client_rsp_ready=0)
        assert self.last['o_error'] and self.last['o_error_code'] == 2
        assert not self.last['o_client_req_ready']
        await self.cycle(fault=('release', 0, 0), i_client_rsp_ready=0)
        for _ in range(100):
            await self.cycle('error_recovery_flush', i_flush=1)
            if self.last['o_flush_completed']:
                break
        else:
            raise AssertionError('Error-recovery flush timed out')
        await self.idle(5, i_error_clear=1)
        assert not self.last['o_error']
        self.active['allow_error'] = False
        await self.send(self.request())
        self.coverage.hit('stale_internal_completion')

    async def power_command(self, target, bank=0, acknowledge=True):
        for _ in range(100):
            item = await self.cycle('power_command', i_bank_power_cmd_valid=1 << bank,
                i_bank_power_state=target << (2 * bank), i_bank_power_ack=0)
            if item.pre['o_bank_power_cmd_ready'] >> bank & 1:
                break
        else:
            raise AssertionError('Power command timed out')
        await self.idle(4, i_bank_power_ack=0)
        if acknowledge:
            for _ in range(100):
                await self.cycle('power_ack')
                if lane(self.last['o_bank_power_state'], 2, bank) == target:
                    await self.idle(2)
                    return
            raise AssertionError('Power transition timed out')

    async def power(self):
        c, cov = self.c, self.coverage
        if not c.SUPPORT_BANK_POWER_GATING:
            assert self.last['o_bank_clock_enable'] == (1 << self.a['B']) - 1
            assert self.last['o_bank_power_cmd_ready'] == 0
            cov.hit('power_disabled')
            return
        await self.drain()
        await self.power_command(1)
        await self.send(self.request())
        await self.power_command(0)
        await self.send(self.request())
        cov.hit('clock_gate_wake')
        if c.SUPPORT_BANK_RETENTION:
            await self.power_command(2)
            await self.power_command(0)
            await self.send(self.request())
            cov.hit('retention')
        item = await self.cycle(i_bank_power_cmd_valid=1, i_bank_power_state=3)
        assert not item.pre['o_bank_power_cmd_ready'] & 1
        cov.hit('off_ownership_refusal')
        for r, d in enumerate(self.active['model'].regions):
            if d['valid']:
                await self.command(4, r)
        await self.power_command(3)
        assert not self.last['o_bank_contents_valid'] & 1
        await self.power_command(0)
        assert not self.last['o_bank_contents_valid'] & 1
        cov.hit('destructive_off')
        await self.command(1, base=0, limit=self.a['capacity'], state=5,
            contents_valid=0, read_mask=(1 << self.a['C']) - 1,
            write_mask=(1 << self.a['C']) - 1, owner_id=5, kernel_id=3)
        await self.send(self.request(opcode=1, data=0x17))
        await self.command(2, contents_valid=1)
        await self.send(self.request())
        cov.hit('reload_after_off')
        if c.SUPPORT_BANK_RETENTION:
            await self.drain()
            await self.power_command(2, acknowledge=False)
            await self.reset()
            assert self.last['o_bank_isolate'] == 0
            cov.hit('reset_power_transition')

    async def body(self):
        await self.setup()
        if self.c.REGION_GENERATION_WIDTH <= 3:
            await self.generation_wrap()
        else:
            await self.directed()
        await self.unknown_controls()
        await self.traffic()
        await self.faults()
        await self.flush()
        await self.recovery()
        await self.stale_completion()
        await self.power()
        await self.drain()
        await self.idle(4)
