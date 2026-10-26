"""Real shell programming and deterministic memory/stream peer scenarios."""
from collections import deque
from copy import deepcopy
import os
from tile_shell.sequences import TileShellSequence
from tile_shell.model import number, crc32c
from mst.model import pack, unpack, positions, convert, stream_beats
from mst.transaction import MstItem, INPUTS


class MstSequence(TileShellSequence):
    def __init__(self, config):
        super().__init__(config)
        self.base = {n: self.base.get(n, 0) for n in INPUTS}
        self.base.update(i_completion_ready=1, i_rejection_ready=1,
            i_region_response_ready=1, i_buffer_response_ready=1,
            i_scratchpad_read_ready=(1 << config.NUM_SCRATCHPAD_CLIENTS) - 1,
            i_scratchpad_write_ready=(1 << config.NUM_SCRATCHPAD_CLIENTS) - 1,
            i_dma_out_ready=(1 << config.NUM_DMA_EGRESS_CHANNELS) - 1)
        self.mem = bytearray((k * 37 + k // 7) & 255 for k in range(65536))
        self.pending = {'read': [], 'write': []}
        self.offers = {'read': {}, 'write': {}}
        self.completions = []
        self.rejections = []
        self.outputs = []
        self.events = []
        self.requests = []
        self.delay = 3
        self.hold_responses = False
        self.error_next = False
        self.partial_next = None
        self.cmd = 0
        self.reference = {}
        self.expected_requests = {}
        self.forbidden = set()
        self.automatic = None
        self.terminal_events = {}
        self.event_sequences = {}

    async def cycle(self, label='idle', *, core_edge=True, cfg_edge=None, fault=None, **ports):
        self.index += 1
        if os.getenv('MST_DEBUG_CYCLES'):
            print(self.index, label, flush=True)
        auto = dict(i_body_save_done=number(self.last.get('o_body_save', '0')) or 0,
                    i_body_restore_done=number(self.last.get('o_body_restore', '0')) or 0,
                    i_body_isolation_ack=number(self.last.get('o_body_isolate', '0')) or 0,
                    i_body_power_good=number(self.last.get('o_body_power_enable', '1')) or 0)
        a = self.c.aliases
        for kind in ('read', 'write'):
            peer = {}
            for client in range(a['NM']):
                if client not in self.offers[kind] and not self.hold_responses:
                    candidates = [r for r in self.pending[kind] if r['client'] == client and
                                  r['due'] <= self.index]
                    if candidates:
                        self.offers[kind][client] = candidates[-1]
                if client in self.offers[kind]:
                    r = self.offers[kind][client]
                    peer['valid'] = peer.get('valid', 0) | 1 << client
                    for name, width in (('tag', a['MT']), ('identity', a['IDW']), ('error', 1)):
                        peer[name] = peer.get(name, 0) | r[name] << (client * width)
                    name = 'data' if kind == 'read' else 'bytes_committed'
                    width = a['MD'] if kind == 'read' else a['MBW']
                    peer[name] = peer.get(name, 0) | r[name] << (client * width)
            auto.update({f'i_scratchpad_{kind}_response_{n}': v for n, v in peer.items()})
        item = MstItem(f'{label}_{self.index}', self.base | auto | ports,
            cfg_edge=(self.index % 3 != 0) if cfg_edge is None else cfg_edge,
            core_edge=core_edge, phase=self.index % 2, fault=fault)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.post
        for domain, raw in item.edges.items():
            p = {n: number(v) for n, v in raw.items()}
            if domain == 'cfg' or domain == 'core' and not self.c.CONFIG_ASYNC:
                if p['o_cfg_response_valid'] and p['i_cfg_response_ready']:
                    self.responses[p['o_cfg_response_tag']] = p
            if domain == 'core':
                if p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
                    self.runtime_responses[p['o_runtime_response_tag']] = p
                if p['i_rstb'] == 1:
                    self.peer(p)
        return item

    def register(self, descriptor):
        p, a = self.c.parameters, self.c.aliases
        identity = pack(p, 'identity', descriptor['identity'])
        self.reference[identity] = deepcopy(descriptor)
        for kind, side, modes in (('read', 'source', (0, 2, 6)),
                                  ('write', 'destination', (1, 2, 5))):
            fragments = deque()
            if descriptor['mode']['transfer'] in modes:
                f = descriptor['format']
                size = f['source_log2' if kind == 'read' else 'destination_log2'] + f['lane_log2']
                for address in positions(descriptor[side], descriptor['mode']['address_mode'],
                                         descriptor['control'], size):
                    length = 1 << size
                    if kind == 'read':
                        first = address // a['MY'] * a['MY']
                        last = (address + length - 1) // a['MY'] * a['MY']
                        fragments.extend((word, a['MY']) for word in range(first, last+1, a['MY']))
                    else:
                        while length:
                            chunk = min(a['MY'], 1 << (length.bit_length() - 1))
                            while address % chunk:
                                chunk //= 2
                            fragments.append((address, chunk))
                            address += chunk
                            length -= chunk
            self.expected_requests[kind, identity] = fragments

    @staticmethod
    def check_terminal_event(event, completion):
        expected = ((completion['status'] << 30) | (completion['error_code'] << 22) |
                    (completion['partial'] << 21) | (completion['overflow'] << 20) |
                    (completion['bytes_written'] & ((1 << 20) - 1)))
        assert event['payload'] == expected, (event, completion)
        assert event['error'] == int(completion['error_code'] != 0)

    def peer(self, p):
        a = self.c.aliases
        for kind in ('read', 'write'):
            for client in range(a['NM']):
                def get(n, w, output=True):
                    return (p[f'{"o" if output else "i"}_scratchpad_{kind}_{n}'] >>
                            (client * w)) & ((1 << w) - 1)
                if (get('response_ready', 1) and get('response_valid', 1, False) and
                        client in self.offers[kind]):
                    r = self.offers[kind].pop(client)
                    if self.pending[kind] and r is not self.pending[kind][0]:
                        self.coverage.hit('out_of_order_response')
                    self.pending[kind].remove(r)
                if get('valid', 1) and get('ready', 1, False):
                    address = get('address', a['A'])
                    size = 1 << get('size_log2', a['MSZ'])
                    identity = get('identity', a['IDW'])
                    tag = get('tag', a['MT'])
                    if identity not in self.reference and self.automatic is not None:
                        d = deepcopy(self.automatic)
                        d['identity'].update(owner=5, kernel=3, package_id=11, context_id=0,
                            allocation=1, version=number(self.last['o_status_context_version']),
                            epoch=number(self.last['o_execution_epoch']))
                        assert identity == pack(self.c.parameters, 'identity', d['identity'])
                        self.register(d)
                    assert identity in self.reference and identity not in self.forbidden
                    expected = self.expected_requests[kind, identity]
                    assert expected, ('Unexpected memory effect', kind, identity, address)
                    assert (address, size) == expected.popleft(), ('Wrong fragment', kind, address, size)
                    d = self.reference[identity]
                    endpoint = d['source' if kind == 'read' else 'destination']
                    assert get('region_id', a['RI']) == endpoint['region_id']
                    assert get('generation', a['DG']) == endpoint['region_generation']
                    assert get('priority', a['PR']) == d['control'].get('priority_hint', 0)

                    assert address % size == 0 and size <= a['MY']
                    assert address + size <= len(self.mem)
                    assert all(r['tag'] != tag for r in self.pending[kind])
                    error = int(self.error_next)
                    self.error_next = False
                    r = dict(client=client, due=self.index + self.delay + self.rng.randrange(4),
                             tag=tag, identity=identity, error=error)
                    self.requests.append((kind, address, size, identity))
                    if kind == 'read':
                        assert size == a['MY']
                        r['data'] = int.from_bytes(self.mem[address:address + size], 'little')
                    else:
                        data = get('data', a['MD'])
                        strobe = get('strobe', a['MY'])
                        assert strobe == ((1 << size) - 1) << (address % a['MY'])
                        committed = size if self.partial_next is None else min(size, self.partial_next)
                        self.partial_next = None
                        r['bytes_committed'] = committed
                        r['error'] |= int(committed != size)
                        for j in range(committed):
                            self.mem[address + j] = (data >> (8 * j)) & 255
                    self.pending[kind].append(r)
        if p['o_completion_valid'] and p['i_completion_ready']:
            c = {n.removeprefix('o_completion_'): v for n, v in p.items()
                 if n.startswith('o_completion_')}
            self.completions.append(c)
            if c['identity'] in self.terminal_events:
                self.check_terminal_event(self.terminal_events[c['identity']], c)
            if c['status'] == 0:
                for kind in ('read', 'write'):
                    assert not self.expected_requests[kind, c['identity']]
        if p['o_rejection_valid'] and p['i_rejection_ready']:
            self.rejections.append((p['o_rejection_identity'], p['o_rejection_code']))
        for group, count, data in (('data', a['NO'], 'payload'), ('dma', a['NDO'], 'data')):
            for k in range(count):
                if (p[f'o_{group}_out_valid'] & p[f'i_{group}_out_ready']) >> k & 1:
                    self.outputs.append((group, k, (p[f'o_{group}_out_{data}'] >> (k * a['D'])) &
                        ((1 << a['D']) - 1), (p[f'o_{group}_out_metadata'] >> (k * a['M'])) &
                        ((1 << a['M']) - 1)))
        if p['o_event_out_valid'] & p['i_event_out_ready']:
            ev = unpack(self.c.parameters, 'event', p['o_event_out_payload'])
            self.events.append(ev)
            if ev['kind'] == 7:
                assert ev['identity'] in self.reference and ev['identity'] not in self.terminal_events
                d = self.reference[ev['identity']]
                assert d['events']['completion_enable'] and ev['id'] == d['events']['completion_id']
                assert ev['context_id'] == d['identity']['context_id'] and ev['kernel'] == 3
                key = d['identity']['epoch'], ev['id']
                assert ev['sequence_id'] > self.event_sequences.get(key, 0)
                self.event_sequences[key] = ev['sequence_id']
                self.terminal_events[ev['identity']] = ev
                for c in self.completions:
                    if c['identity'] == ev['identity']:
                        self.check_terminal_event(ev, c)


    async def reset(self, cfg_only=False, fault=None):
        self.pending = {'read': [], 'write': []}
        self.offers = {'read': {}, 'write': {}}
        self.reference.clear()
        self.expected_requests.clear()
        self.forbidden.clear()
        self.terminal_events.clear()
        self.event_sequences.clear()
        self.automatic = None
        self.base['i_data_in_valid'] = self.base['i_dma_in_valid'] = 0
        await super().reset(cfg_only, fault)
        self.completions.clear()
        self.rejections.clear()
        self.outputs.clear()
        self.events.clear()
        self.requests.clear()
        self.coverage.hit('reset')

    async def setup(self, *, automatic=None, terminal=0):
        await self.reset()
        self.automatic = deepcopy(automatic)
        assert not number((await self.runtime(0))['o_runtime_response_error'])
        a, p = self.c.aliases, self.c.parameters
        r = dict(valid=1, generation=1, space=0, base=0, limit=len(self.mem), owner=5,
                 kernel=3, allocation=1, read_enable=1, write_enable=1, dma_enable=1,
                 channel_mask=(1 << (1 << a['CH'])) - 1, buffer_mask=(1 << a['NB']) - 1)
        await self.management('region', 0, pack(p, 'region', r))
        context = dict(schema=1, package_id=11, allocation=1, loads=(1 << a['NL']) - 1,
            stores=(1 << a['NS']) - 1, regions=1, terminal=terminal,
            automatic_command=int(automatic is not None),
            descriptor=automatic or 0)
        image = pack(p, 'context', context)
        for word in range(self.c.CONFIG_WORD_COUNT):
            response = await self.cfg(0, 0, word,
                (image >> (word * self.c.CONFIG_DATA_WIDTH)) & ((1 << self.c.CONFIG_DATA_WIDTH) - 1))
            assert not number(response['o_cfg_response_error'])
        crc = crc32c(image.to_bytes(a['IM'] // 8, 'little'))
        response = await self.cfg(2, 0, crc=crc)
        assert not number(response['o_cfg_response_error']), response
        assert not number((await self.cfg(3))['o_cfg_response_error'])
        assert not number((await self.runtime(1))['o_runtime_response_error'])
        await self.idle(6)
        self.coverage.hit('context')

    async def management(self, kind, index, record, *, error=False):
        for _ in range(100):
            item = await self.cycle(kind, **{f'i_{kind}_valid': 1,
                f'i_{kind}_index': index, f'i_{kind}_record': record})
            if number(item.edges['core'][f'o_{kind}_ready']):
                break
        else:
            raise AssertionError(f'{kind} management blocked')
        if number(self.last[f'o_{kind}_response_valid']):
            assert bool(number(self.last[f'o_{kind}_response_error'])) == error
        else:
            raise AssertionError(f'{kind} response missing')
        await self.idle(2)
        self.coverage.hit(kind)

    def descriptor(self, mode=0, *, count=3, source=128, destination=1024,
                   source_log2=0, destination_log2=None, lane_log2=0):
        self.cmd += 1
        load = mode in (0, 2, 3, 6)
        src_space = 0 if mode in (0, 2, 6) else 3 if mode in (3, 5) else 2
        dst_space = 0 if mode in (1, 2, 5) else 3 if mode in (4, 6) else 2
        return dict(identity=dict(command=self.cmd, generation=1, owner=5, kernel=3,
            package_id=11, context_id=0, version=number(self.last['o_status_context_version']),
            allocation=1, epoch=number(self.last['o_execution_epoch'])),
            mode=dict(transfer=mode, address_mode=0, load_channel=0, store_channel=0),
            source=dict(space=src_space, channel=0, base=source, region_id=0, region_generation=1),
            destination=dict(space=dst_space, channel=0, base=destination,
                             region_id=0, region_generation=1),
            format=dict(source_log2=source_log2,
                destination_log2=source_log2 if destination_log2 is None else destination_log2,
                lane_log2=lane_log2, eos=1), events=dict(completion_enable=1, completion_id=0),
            control=dict(inner_count=count, outer_count=1, cancelable=self.c.SUPPORT_CANCELLATION))

    async def submit(self, d, *, error=0):
        p = self.c.parameters
        if os.getenv('MST_DEBUG_CYCLES'):
            print('SUBMIT', d['identity'], 'expected', error, flush=True)
        n = len(self.rejections)
        identity = pack(p, 'identity', d['identity'])
        if not error:
            self.register(d)
        elif identity not in self.reference:
            self.forbidden.add(identity)
        ports = {'i_descriptor_valid': 1}
        for group, value in d.items():
            ports['i_descriptor_' + group] = pack(p,
                'endpoint' if group in ('source', 'destination') else group, value)
        for _ in range(500):
            item = await self.cycle('descriptor', **ports)
            if number(item.edges['core']['o_descriptor_ready']):
                break
        else:
            raise AssertionError(('Descriptor admission timed out', {n: number(v) for n, v in
                self.last.items() if n.startswith('o_') and ('status' in n or 'mst' in n or
                'clock' in n or 'descriptor' in n)}))
        await self.idle(2)
        if error:
            assert self.rejections[n:] == [(pack(p, 'identity', d['identity']), error)], self.rejections
        else:
            assert len(self.rejections) == n, self.rejections[n:]

    async def finish(self, d, *, status=0, code=0, limit=2000):
        ident = pack(self.c.parameters, 'identity', d['identity'])
        for _ in range(limit):
            found = [c for c in self.completions if c['identity'] == ident]
            if found:
                assert len(found) == 1
                assert found[0]['status'] == status and found[0]['error_code'] == code, (str(found), d)
                await self.idle(8)
                return found[0]
            await self.cycle('wait_completion')
        raise AssertionError(('Completion timeout', d, self.requests, self.outputs,
            {n: number(v) for n, v in self.last.items() if n.startswith('o_') and
             ('status' in n or 'mst' in n or 'occupancy' in n)}))

    async def transfer(self, d, *, values=None):
        p, a = self.c.parameters, self.c.aliases
        f, ctl, mode = d['format'], d['control'], d['mode']['transfer']
        count = ctl['inner_count'] * ctl['outer_count']
        source_size = f['source_log2'] + f['lane_log2']
        destination_size = f['destination_log2'] + f['lane_log2']
        if mode in (0, 2, 6):
            addresses = positions(d['source'], d['mode']['address_mode'], ctl, source_size)
            values = [int.from_bytes(self.mem[x:x + (1 << source_size)], 'little') for x in addresses]
        elif values is None:
            values = [self.rng.getrandbits(8 << source_size) for _ in range(count)]
        converted = [convert(v, f['source_log2'], f['destination_log2'], f['lane_log2'],
            signed_mode=f.get('signed_mode', 0), saturate=f.get('saturate', 0),
            reverse=f.get('reverse', 0)) for v in values]
        expected = [v for v, _ in converted]
        overflow = any(flag for _, flag in converted)
        before = len(self.outputs)
        await self.submit(d)
        if mode not in (0, 2, 6):
            group = 'dma' if d['source']['space'] == 3 else 'data'
            channel = d['source']['channel']
            for data, metadata in stream_beats(p, d, values, source=True):
                for _ in range(1000):
                    item = await self.cycle('source', **{f'i_{group}_in_valid': 1 << channel,
                        f'i_{group}_in_{"data" if group == "dma" else "payload"}': data << (channel*a['D']),
                        f'i_{group}_in_metadata': metadata << (channel*a['M'])})
                    if number(item.edges['core'][f'o_{group}_in_ready']) >> channel & 1:
                        break
                else:
                    raise AssertionError('Source stalled')
        completion = await self.finish(d)
        assert completion['bytes_read'] == count * (1 << source_size), completion
        assert completion['bytes_written'] == count * (1 << destination_size), completion
        assert completion['elements'] == count, completion
        assert bool(completion['overflow']) == overflow, completion
        assert bool(completion['saturated']) == bool(overflow and f.get('saturate')), completion
        if mode in (1, 2, 5):
            addresses = positions(d['destination'], d['mode']['address_mode'], ctl, destination_size)
            for address, value in zip(addresses, expected, strict=True):
                assert int.from_bytes(self.mem[address:address + (1 << destination_size)], 'little') == value
        else:
            group = 'dma' if d['destination']['space'] == 3 else 'data'
            actual = [(data, meta) for g, ch, data, meta in self.outputs[before:]
                      if g == group and ch == d['destination']['channel']]
            assert actual == stream_beats(p, d, expected), (d, actual, stream_beats(p, d, expected))
        self.coverage.hit({0:'load', 1:'store', 2:'copy', 3:'dma', 4:'dma', 5:'dma', 6:'dma',
                           7:'forward'}[mode])

    async def feed(self, d, values):
        a, p = self.c.aliases, self.c.parameters
        group = 'dma' if d['source']['space'] == 3 else 'data'
        channel = d['source']['channel']
        for data, metadata in stream_beats(p, d, values, source=True):
            for _ in range(1000):
                item = await self.cycle('feed', **{f'i_{group}_in_valid': 1 << channel,
                    f'i_{group}_in_{"data" if group == "dma" else "payload"}': data << (channel*a['D']),
                    f'i_{group}_in_metadata': metadata << (channel*a['M'])})
                if number(item.edges['core'][f'o_{group}_in_ready']) >> channel & 1:
                    break
            else:
                raise AssertionError('Source stalled')

    async def power(self, state):
        for _ in range(100):
            item = await self.cycle('power_request', i_power_request_valid=1,
                                    i_power_request_state=state)
            if number(item.edges['core']['o_power_request_ready']):
                break
        else:
            raise AssertionError('Power request timed out')
        for _ in range(160):
            item = await self.cycle('power_wait')
            response = item.edges['core']
            if number(response['o_power_response_valid']):
                assert not number(response['o_power_response_error']), (state, response)
                break
        else:
            raise AssertionError(f'Power transition {state} timed out')
        await self.idle(6)


    async def extra_cases(self):
        p, a = self.c.parameters, self.c.aliases
        for change, code in ((('identity', 'owner', 4), 2),
                             (('mode', 'address_mode', 3), 3),
                             (('control', 'inner_count', 0), 5),
                             (('source', 'region_generation', 0), 10)):
            d = self.descriptor(count=1)
            group, field, value = change
            d[group][field] = value
            await self.submit(d, error=code)
        if self.c.SUPPORT_LOCAL_COPY:
            d = self.descriptor(2, count=2, source=128, destination=128)
            await self.submit(d, error=13)
        self.coverage.hit('rejection_matrix')
        d = self.descriptor(count=1)
        ports = {'i_descriptor_' + n: pack(p,
            'endpoint' if n in ('source', 'destination') else n, v) for n, v in d.items()}
        ports['i_descriptor_format'] = 'x' * a['FOW']
        before = len(self.rejections)
        await self.cycle('unknown_descriptor', i_descriptor_valid=1, **ports)
        await self.idle(3)
        assert self.rejections[before:] == [(pack(p, 'identity', d['identity']), 1)]
        self.coverage.hit('unknown_descriptor')

        d = self.descriptor(1, count=1)
        await self.submit(d)
        wrong = deepcopy(d)
        wrong['identity']['command'] += 1
        before = len(self.requests)
        await self.feed(wrong, [42])
        result = await self.finish(d, status=1, code=14)
        assert result['bytes_written'] == 0 and len(self.requests) == before
        self.coverage.hit('malformed_stream')
        # An advertised physical request is irrevocable even when cancellation
        # arrives while its ready is low.
        self.base['i_scratchpad_read_ready'] = 0
        d = self.descriptor(count=1)
        await self.submit(d)
        await self.idle(18)
        assert number(self.last['o_scratchpad_read_valid'])
        self.base['i_scratchpad_read_ready'] = (1 << a['NM']) - 1
        await self.finish(d)
        if self.c.MAX_OUTSTANDING_READS > 1:
            d = self.descriptor(count=3)
            before = len(self.outputs)
            expected = stream_beats(p, d, [self.mem[128+k] for k in range(3)])
            self.hold_responses = True
            await self.submit(d)
            await self.idle(18)
            self.hold_responses = False
            await self.finish(d)
            assert [(v, m) for g, ch, v, m in self.outputs[before:] if g == 'data'] == expected
        # Terminal event backpressure keeps the command's identity reserved even
        # after its completion response has been consumed.
        d = self.descriptor(count=1)
        self.base['i_event_out_ready'] = 0
        await self.submit(d)
        await self.finish(d)
        await self.submit(d, error=16)
        self.base['i_event_out_ready'] = 1
        await self.idle(10)
        assert number(self.last['o_mst_quiescent'])
        self.coverage.hit('reliable_event')
        if self.c.SUPPORT_COMMAND_CHAINING and a['NE'] >= 4:
            first = self.descriptor(count=1)
            second = self.descriptor(count=1)
            first['events'].update(completion_id=2, chain_enable=1,
                chain_command=second['identity']['command'], chain_generation=1)
            second['events'].update(completion_id=3, start=1, mask=4,
                dependency=first['identity']['command'], dependency_generation=1)
            await self.submit(first)
            await self.submit(second)
            await self.finish(first)
            await self.finish(second)
            self.coverage.hit('chain')
        if self.c.SUPPORT_DOUBLE_BUFFER:
            b = dict(valid=1, generation=1, state=0, space=0, region_id=0,
                base=1024, limit=2048, owner=5, kernel=3, package_id=11, context_id=0, allocation=1)
            await self.management('buffer', 0, pack(p, 'buffer', b))
            d = self.descriptor(1, count=3)
            d['destination'].update(buffer_enable=1, buffer_id=0, buffer_generation=1)
            await self.transfer(d)
            d = self.descriptor(0, count=3, source=1024)
            d['source'].update(buffer_enable=1, buffer_id=0, buffer_generation=3)
            await self.transfer(d)
            stale = self.descriptor(1, count=1)
            stale['destination'].update(buffer_enable=1, buffer_id=0, buffer_generation=1)
            await self.submit(stale, error=12)
            self.coverage.hit('buffer_roles')
        # A partial write acknowledgement is authoritative for committed bytes.
        if self.c.MAX_ELEMENT_BYTES >= 2:
            d = self.descriptor(1, count=1, source_log2=1)
            self.partial_next = 1
            await self.submit(d)
            await self.feed(d, [0xa1b2])
            c = await self.finish(d, status=1, code=17)
            assert c['bytes_written'] == 1 and c['partial'] and self.mem[1024] == 0xb2
            self.coverage.hit('partial_write')
        # Unrelated channels share a physical endpoint but keep ordering,
        # immutable metadata, and completion ownership separate.
        if a['NL'] >= 2 and a['NO'] >= 2:
            ds = [self.descriptor(count=3, source=256 + 16*k) for k in range(2)]
            expected = {}
            for k, d in enumerate(ds):
                d['mode']['load_channel'] = k
                d['destination']['channel'] = k
                values = [self.mem[d['source']['base'] + n] for n in range(3)]
                expected[k] = stream_beats(p, d, values)
            before = len(self.outputs)
            for d in ds:
                await self.submit(d)
            for d in ds:
                await self.finish(d)
            for k in range(2):
                assert [(v, m) for g, ch, v, m in self.outputs[before:]
                        if g == 'data' and ch == k] == expected[k]
            self.coverage.hit('concurrent_channels')
        if self.c.SUPPORT_CANCELLATION and self.c.SUPPORT_EVENT_START:
            # The second descriptor cannot jump its channel's waiting head.
            ds = [self.descriptor(count=1) for _ in range(self.c.COMMAND_QUEUE_DEPTH)]
            for d in ds:
                d['events'].update(start=1, mask=2, dependency=123, dependency_generation=1)
                await self.submit(d)
            extra = self.descriptor(count=1)
            ports = {'i_descriptor_' + n: pack(p,
                'endpoint' if n in ('source', 'destination') else n, v) for n, v in extra.items()}
            item = await self.cycle('queue_full', i_descriptor_valid=1, **ports)
            assert number(item.edges['core']['o_descriptor_ready']) == 0
            victim = ds[-1]
            await self.cycle('queued_cancel', i_cancel_valid=1,
                i_cancel_identity=pack(p, 'identity', victim['identity']))
            assert number(self.last['o_cancel_accepted'])
            await self.cycle('flush', i_flush=1)
            for d in ds:
                await self.finish(d, status=2, code=20)
            await self.idle(10)
            assert number(self.last['o_mst_quiescent'])
            self.coverage.hit('queue_flush')
        # No memory response for a defined interval invokes timeout cancellation;
        # accepted physical obligations still have to return before completion.
        if self.c.TRANSFER_TIMEOUT_CYCLES >= 24:
            d = self.descriptor(count=2)
            d['control']['timeout'] = 20
            self.hold_responses = True
            await self.submit(d)
            await self.idle(25)
            assert not any(c['identity'] == pack(p, 'identity', d['identity'])
                           for c in self.completions)
            self.hold_responses = False
            await self.finish(d, status=1, code=19)
            self.coverage.hit('timeout')
        # Suspension preserves a waiting command. The shell may suspend only at
        # a boundary with no launched command or outstanding physical effects.
        if self.c.SUPPORT_EVENT_START:
            d = self.descriptor(count=1)
            d['events'].update(start=1, mask=2, dependency=124, dependency_generation=1)
            await self.submit(d)
            result = await self.runtime(2)
            assert not number(result['o_runtime_response_error'])
            assert number(self.last['o_status_execution_state']) == 9
            assert not number((await self.runtime(3))['o_runtime_response_error'])
            ev = pack(p, 'event', dict(kind=7, context_id=0, kernel=3, id=1, sequence_id=7,
                identity=pack(p, 'identity', d['identity'] | dict(command=124))))
            for _ in range(100):
                item = await self.cycle('resume_event', i_event_in_valid=1, i_event_in_payload=ev)
                if number(item.edges['core']['o_event_in_ready']):
                    break
            await self.finish(d)
            self.coverage.hit('suspend_resume')
        if self.c.SUPPORT_RETENTION:
            assert not number((await self.runtime(2))['o_runtime_response_error'])
            await self.power(3)
            assert number(self.last['o_status_power_state']) == 3
            await self.power(0)
            assert not number((await self.runtime(3))['o_runtime_response_error'])
            await self.idle(8)
            self.coverage.hit('retention')
        # A runtime terminate returns READY before pending responses arrive.
        # Terminal body events must still drain through that shell state.
        d = self.descriptor(count=3)
        self.hold_responses = True
        await self.submit(d)
        await self.idle(12)
        assert not number((await self.runtime(5))['o_runtime_response_error'])
        self.hold_responses = False
        await self.finish(d, status=2, code=20)
        await self.idle(20)
        assert number(self.last['o_mst_quiescent'])
        self.coverage.hit('terminate_drain')
        assert not number((await self.runtime(1))['o_runtime_response_error'])
        await self.idle(8)
        # The public debug path snapshots lifetime counters under shell ownership.
        for address in (0x80, 0x82, 0x83, 0x90, 0x91, 0xa0):
            for _ in range(100):
                item = await self.cycle('counter', i_debug_request_valid=1,
                    i_debug_request_address=address, i_debug_request_owner_id=5)
                if number(item.edges['core']['o_debug_request_ready']):
                    break
            assert number(self.last['o_debug_response_valid'])
            assert not number(self.last['o_debug_response_error'])
            assert number(self.last['o_debug_response_read_data']) > 0
            if address in (0x90, 0x91):
                field = 'bytes_read' if address == 0x90 else 'bytes_written'
                expected = min(0xffffffff, sum(c[field] for c in self.completions))
                assert number(self.last['o_debug_response_read_data']) == expected, field
            await self.idle(2)
        self.coverage.hit('counters')

    async def body(self):
        await self.setup()
        for mode in range(8):
            if mode != 2 or self.c.SUPPORT_LOCAL_COPY:
                await self.transfer(self.descriptor(mode))
        # Force visible output backpressure while memory responses retire.
        self.base['i_data_out_ready'] = 0
        d = self.descriptor(count=1)
        await self.submit(d)
        await self.idle(40)
        assert not any(c['identity'] == pack(self.c.parameters, 'identity', d['identity'])
                       for c in self.completions)
        self.base['i_data_out_ready'] = (1 << self.c.NUM_STREAM_OUTPUTS) - 1
        await self.finish(d)
        self.coverage.hit('backpressure')
        d = self.descriptor()
        d['source']['base'] = len(self.mem) - 1
        d['control']['inner_count'] = 2
        await self.submit(d, error=10)
        self.coverage.hit('bounds')
        if self.c.SUPPORT_UNALIGNED:
            for offset in range(min(8, self.c.MEMORY_DATA_WIDTH // 8)):
                await self.transfer(self.descriptor(0, source=129+offset, source_log2=min(1, self.c.aliases['LOG'])))
                await self.transfer(self.descriptor(1, destination=1025+offset, source_log2=min(1, self.c.aliases['LOG'])))
            self.coverage.hit('unaligned')
        if self.c.SUPPORT_ELEMENT_CONVERSION:
            for signed in (0, 1):
                for saturation in (0, 1):
                    d = self.descriptor(7, source_log2=min(1, self.c.aliases['LOG']), destination_log2=0,
                                        lane_log2=max(0, min(1, self.c.aliases['LOG'] - 1)))
                    d['format'].update(signed_mode=signed, saturate=saturation, reverse=1)
                    await self.transfer(d)
            self.coverage.hit('conversion')
        if self.c.SUPPORT_2D:
            d = self.descriptor(0, count=3, source=256)
            d['mode']['address_mode'] = 2
            d['source'].update(inner_stride=-2, outer_stride=16)
            d['control']['outer_count'] = 2
            await self.transfer(d)
            self.coverage.hit('two_dimensional')
        # A held terminal record retains its immutable identity and duplicate key.
        self.base['i_completion_ready'] = 0
        d = self.descriptor(count=1)
        await self.submit(d)
        await self.idle(60)
        await self.submit(d, error=16)
        self.base['i_completion_ready'] = 1
        await self.finish(d)
        self.coverage.hit('duplicate')
        if self.c.SUPPORT_EVENT_START:
            d = self.descriptor(count=1)
            d['events'].update(start=1, mask=2, dependency=55, dependency_generation=1)
            await self.submit(d)
            n = len(self.requests)
            await self.idle(10)
            assert len(self.requests) == n
            identity = d['identity'] | dict(command=55)
            event = pack(self.c.parameters, 'event', dict(kind=7, context_id=0, kernel=3,
                id=1, sequence_id=1, identity=pack(self.c.parameters, 'identity', identity)))
            for _ in range(100):
                item = await self.cycle('event', i_event_in_valid=1, i_event_in_payload=event)
                if number(item.edges['core']['o_event_in_ready']):
                    break
            await self.finish(d)
            self.coverage.hit('event')
        if self.c.SUPPORT_CANCELLATION:
            d = self.descriptor(count=10)
            self.hold_responses = True
            await self.submit(d)
            await self.idle(20)
            ident = pack(self.c.parameters, 'identity', d['identity'])
            for _ in range(100):
                item = await self.cycle('cancel', i_cancel_valid=1, i_cancel_identity=ident)
                if number(item.edges['core']['o_cancel_ready']):
                    break
            self.hold_responses = False
            await self.finish(d, status=2, code=20)
            self.coverage.hit('cancel')
        await self.extra_cases()
        for _ in range(self.c.random_cycles):
            mode = self.rng.randrange(8)
            if mode == 2 and not self.c.SUPPORT_LOCAL_COPY:
                mode = 0
            size = self.rng.randrange(min(self.c.aliases['LOG'], 3) + 1)
            size = min(size, (self.c.MAX_ELEMENT_BYTES - 1).bit_length())
            await self.transfer(self.descriptor(mode, count=self.rng.randrange(1, 6),
                source=128 + (self.rng.randrange(8) if self.c.SUPPORT_UNALIGNED else 0),
                destination=1024 + (self.rng.randrange(8) if self.c.SUPPORT_UNALIGNED else 0),
                source_log2=size))
        await self.idle(20)
        assert number(self.last['o_mst_quiescent'])
        assert not any(self.pending.values())
        automatic = self.descriptor(count=1)
        await self.setup(automatic=automatic, terminal=1)
        automatic['identity'].update(version=number(self.last['o_status_context_version']),
                                     epoch=number(self.last['o_execution_epoch']))
        await self.finish(automatic)
        await self.idle(20)
        assert number(self.last['o_status_execution_state']) == 11
        self.coverage.hit('automatic_context')
        if self.c.CANCEL_TIMEOUT_CYCLES <= 64:
            await self.setup()
            d = self.descriptor(count=1)
            self.hold_responses = True
            await self.submit(d)
            await self.idle(15)
            self.active['allow_fatal'] = True
            await self.cycle('cancel_deadline', i_cancel_valid=1,
                i_cancel_identity=pack(self.c.parameters, 'identity', d['identity']))
            await self.idle(self.c.CANCEL_TIMEOUT_CYCLES + 8)
            assert number(self.last['o_mst_fatal_error'])
            result = [c for c in self.completions if c['identity'] ==
                      pack(self.c.parameters, 'identity', d['identity'])]
            assert len(result) == 1 and result[0]['status'] == 3
            assert result[0]['effects_unknown'] == 1
            assert not number(self.last['o_mst_idle'])
            assert not number(self.last['o_descriptor_ready'])
            self.hold_responses = False
            await self.reset()
            self.active['allow_fatal'] = False
            self.coverage.hit('cancel_containment')
        self.active['allow_fatal'] = True
        await self.cycle('stale_response', i_scratchpad_read_response_valid=1,
                         i_scratchpad_read_response_tag=0, i_scratchpad_read_response_identity=0)
        assert number(self.last['o_mst_fatal_error'])
        assert not number(self.last['o_scratchpad_read_valid'])
        assert not number(self.last['o_scratchpad_write_valid'])
        await self.reset()
        self.active['allow_fatal'] = False
        self.coverage.hit('stale_tag_containment')
        if self.c.CONTROL_PROTECTION:
            self.active['allow_fatal'] = True
            if self.c.CONTROL_PROTECTION == 2:
                await self.cycle('corrected_control', fault=('control', 0, 1))
                assert not number(self.last['o_mst_fatal_error'])
                await self.cycle(fault=('release', 0, 0))
                await self.idle(3)
            mask = 3 if self.c.CONTROL_PROTECTION == 2 else 1
            await self.cycle('fatal_control', fault=('control', 0, mask))
            assert number(self.last['o_mst_fatal_error'])
            await self.cycle(fault=('release', 0, 0))
            await self.reset()
            self.active['allow_fatal'] = False
            self.coverage.hit('control_protection')

