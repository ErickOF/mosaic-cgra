"""Independent command semantics, CRC arithmetic and per-port ownership ledgers."""
from collections import deque
from tile_shell.defaults import DEFAULTS


def number(raw):
    if isinstance(raw, int):
        return raw
    return int(raw, 2) if set(raw.lower()) <= {'0', '1'} else None


def crc32c(image: bytes) -> int:
    # Polynomial long division in normal (MSB-first) form is independent of the
    # reflected RTL recurrence. Reverse each byte and the final register.
    reverse = lambda n, w: int(f'{n:0{w}b}'[::-1], 2)
    state = 0xffffffff
    for byte in image:
        state ^= reverse(byte, 8) << 24
        for _ in range(8):
            state = ((state << 1) ^ (0x1edc6f41 if state & 0x80000000 else 0)) & 0xffffffff
    return reverse(state, 32) ^ 0xffffffff


class ShellModel:
    def __init__(self, c):
        self.c = c
        self.accepted = self.delivered = self.discarded = 0
        self.groups = dict(data_in=('DATA_INPUT_PORTS', 'DATA_WIDTH', 'DATA_METADATA_WIDTH', True),
            data_out=('DATA_OUTPUT_PORTS', 'DATA_WIDTH', 'DATA_METADATA_WIDTH', False),
            predicate_in=('PREDICATE_INPUT_PORTS', 'PREDICATE_WIDTH', 'PREDICATE_METADATA_WIDTH', True),
            predicate_out=('PREDICATE_OUTPUT_PORTS', 'PREDICATE_WIDTH', 'PREDICATE_METADATA_WIDTH', False),
            event_in=('EVENT_INPUT_PORTS', 'EVENT_WIDTH', None, True),
            event_out=('EVENT_OUTPUT_PORTS', 'EVENT_WIDTH', None, False))
        self.reset()

    def reset(self):
        if hasattr(self, 'queues'):
            self.discarded += sum(len(q) for queues in self.queues.values() for q in queues)
        self.queues = {g: [deque() for _ in range(getattr(self.c, dims[0]))]
                       for g, dims in self.groups.items()}
        self.images = [[0] * self.c.CONFIG_WORD_COUNT for _ in range(self.c.CONTEXT_DEPTH)]
        self.written = [0] * self.c.CONTEXT_DEPTH
        self.versions = [0] * self.c.CONTEXT_DEPTH
        self.validated = [False] * self.c.CONTEXT_DEPTH
        self.owner = self.kernel = None
        self.active = None
        self.state = 0
        self.cfg_responses = {}
        self.runtime_responses = deque()
        self.validations = deque()
        self.completions = 0

    def image(self, context):
        return b''.join(word.to_bytes(self.c.CONFIG_DATA_WIDTH // 8, 'little')
                        for word in self.images[context])

    def config(self, p):
        c = self.c
        command, tile, owner, ctx, word, data, strobe, crc, tag = (p['i_cfg_request_' + n] for n in
            ('command', 'tile_id', 'owner_id', 'context_id', 'word_index', 'write_data',
             'write_strobe', 'expected_crc', 'tag'))
        assert tag not in self.cfg_responses, 'Configuration tag reused while owned'
        error = 2 if tile != c.TILE_ID else 3 if self.owner is not None and owner != self.owner else \
            4 if ctx >= c.CONTEXT_DEPTH else 11 if command > 5 else \
            5 if command in (0, 1) and word >= c.CONFIG_WORD_COUNT else 0
        result = dict(command=command, context_id=ctx, tag=tag, error_code=error, read_data=0,
                      context_version=self.versions[ctx] if ctx < c.CONTEXT_DEPTH else self.versions[0], crc=0)
        if not error:
            if command in (0, 4) and ctx == self.active:
                error = 6
            elif command == 0 and self.versions[ctx] == (1 << c.CONTEXT_VERSION_WIDTH) - 1:
                error = 18
            elif command == 2:
                if self.written[ctx] != (1 << c.CONFIG_WORD_COUNT) - 1:
                    error = 7
                elif c.SUPPORT_CONTEXT_CHECKSUM and crc32c(self.image(ctx)) != crc:
                    error = 8
            elif command == 3:
                if self.owner is None:
                    error = 3
                elif not self.validated[ctx]:
                    error = 4
                elif self.state not in (1, 2, 9, 11):
                    error = 12
            if not error:
                if command == 0:
                    mask = sum(255 << (8 * b) for b in range(c.CONFIG_DATA_WIDTH // 8) if strobe >> b & 1)
                    self.images[ctx][word] = (self.images[ctx][word] & ~mask) | (data & mask)
                    self.written[ctx] |= 1 << word
                    self.versions[ctx] += 1
                    self.validated[ctx] = False
                    result['context_version'] = self.versions[ctx]
                elif command == 1:
                    result['read_data'] = self.images[ctx][word]
                elif command == 2:
                    snapshot = dict(context=ctx, version=self.versions[ctx], image=self.image(ctx), tag=tag,
                                    crc=crc32c(self.image(ctx)), sent=False)
                    self.validations.append(snapshot)
                    result = None
                elif command == 3:
                    self.active = ctx
                    self.state = 9 if self.state == 9 else 2
                elif command == 4:
                    self.validated[ctx] = False
                elif command == 5:
                    result.update(read_data=(self.written[ctx] | int(self.validated[ctx]) << c.CONFIG_WORD_COUNT) &
                                  ((1 << c.CONFIG_DATA_WIDTH) - 1), crc=crc32c(self.image(ctx)))
        if result is not None:
            result['error_code'] = error
        self.cfg_responses[tag] = result
        return command, error

    def validate(self, p):
        if p['o_body_validate_valid']:
            assert self.validations, 'Unowned body validation'
            v = self.validations[0]
            assert p['o_body_validate_context_id'] == v['context']
            assert p['o_body_validate_context_version'] == v['version']
            assert p['o_body_validate_context_image'] == int.from_bytes(v['image'], 'little')
            assert p['o_body_validate_word_valid'] == (1 << self.c.CONFIG_WORD_COUNT) - 1
            if p['i_body_validate_ready']:
                v['sent'] = True
        if p['i_body_validate_result_valid'] and p['o_body_validate_result_ready']:
            assert self.validations and self.validations[0]['sent']
            v = self.validations.popleft()
            ctx = v['context']
            error = 10 if (p['i_body_validate_context_id'] != ctx or
                p['i_body_validate_context_version'] != v['version'] or self.versions[ctx] != v['version']) else \
                0 if p['i_body_validate_legal'] else p['i_body_validate_error_code'] or 9
            if not error:
                self.validated[ctx] = True
            self.cfg_responses[v['tag']] = dict(command=2, context_id=ctx, tag=v['tag'],
                read_data=0, context_version=v['version'], crc=v['crc'], error_code=error)

    def runtime(self, p):
        command, owner, kernel, context, tag = (p['i_runtime_request_' + n] for n in
                                              ('command', 'owner_id', 'kernel_id', 'context_id', 'tag'))
        error = 0
        state = self.state
        if command == 0:
            error = 12 if self.owner is not None else 0
            if not error:
                self.owner, self.kernel, self.state = owner, kernel, 1
        elif self.owner is None or (owner, kernel) != (self.owner, self.kernel):
            error = 3
        elif command == 1:
            error = 12 if self.active is None or context != self.active or state not in (2, 11) or p['o_status_error'] else 0
            if not error:
                self.state = 3
        elif command == 2:
            error = 0 if state == 3 else 12
            if not error:
                self.state = 8
        elif command == 3:
            error = 0 if state == 9 else 12
            if not error:
                self.state = 3
        elif command == 4:
            error = 0 if state in (3, 9) else 12
            if not error:
                self.state = 10
        elif command == 5:
            self.state = 2 if self.active is not None else 1
        elif command == 6:
            error = 0 if state in (1, 2, 11, 12) else 12
            if not error:
                self.owner = self.kernel = self.active = None
                self.state = 0
                self.validated = [False] * self.c.CONTEXT_DEPTH
                self.versions = [version + 1 for version in self.versions]
        elif command == 7:
            error = 12 if p['o_status_fatal_error'] else 0
        target = self.state
        if not error and command in (2, 4):
            target = 9 if command == 2 else 2
        self.runtime_responses.append(dict(command=command, state=target,
            error_code=error, tag=tag))
        return command, error

    def cancel_validation(self, error):
        while self.validations:
            v = self.validations.popleft()
            self.cfg_responses[v['tag']] = dict(command=2, context_id=v['context'], tag=v['tag'],
                read_data=0, context_version=v['version'], crc=v['crc'], error_code=error)

    def transfers(self, p, flush):
        if flush:
            self.discarded += sum(len(q) for queues in self.queues.values() for q in queues)
            for queues in self.queues.values():
                for q in queues:
                    q.clear()
            return []
        transfers = []
        for group, (ports, width, metadata, incoming) in self.groups.items():
            source = 'i_' + ('' if incoming else 'body_') + group
            dest = 'o_' + ('body_' if incoming else '') + group
            source_ready = 'o_' + ('' if incoming else 'body_') + group + '_ready'
            dest_ready = 'i_' + ('body_' if incoming else '') + group + '_ready'
            width = getattr(self.c, width)
            mw = getattr(self.c, metadata) if metadata else 0
            for port, queue in enumerate(self.queues[group]):
                push = p[source + '_valid'] is not None and p[source + '_valid'] >> port & 1 and p[source_ready] >> port & 1
                valid = p[dest + '_valid'] >> port & 1
                ready = p[dest_ready] is not None and p[dest_ready] >> port & 1
                if push:
                    payload = (p[source + '_payload'] >> (port * width)) & ((1 << width) - 1)
                    meta = (p[source + '_metadata'] >> (port * mw)) & ((1 << mw) - 1) if metadata else 0
                    queue.append((payload, meta))
                    self.accepted += 1
                    transfers.append((group, port, 'accept'))
                if valid:
                    payload = (p[dest + '_payload'] >> (port * width)) & ((1 << width) - 1)
                    meta = (p[dest + '_metadata'] >> (port * mw)) & ((1 << mw) - 1) if metadata else 0
                    notification = group == 'event_out' and port == 0 and payload & 7 in (0, 5, 6)
                    depth = self.c.INPUT_BUFFER_DEPTH if incoming else self.c.OUTPUT_BUFFER_DEPTH
                    if group.startswith('event'):
                        depth = max(1, depth)
                    if not notification and depth == 0 and not ready:
                        expected_payload = (p[source + '_payload'] >> (port * width)) & ((1 << width) - 1)
                        expected_meta = (p[source + '_metadata'] >> (port * mw)) & ((1 << mw) - 1) if metadata else 0
                        assert (payload, meta) == (expected_payload, expected_meta)
                        continue
                    if not notification:
                        assert queue, f'Unowned {group}[{port}] output'
                        assert (payload, meta) == queue[0], f'Reordered or changed {group}[{port}] output'
                        if ready:
                            queue.popleft()
                            self.delivered += 1
                            transfers.append((group, port, 'deliver'))
                    elif ready and payload & 7 == 0:
                        self.completions += 1
                        self.state = 11
                        if self.runtime_responses and self.runtime_responses[0]['command'] == 4:
                            self.runtime_responses[0]['state'] = 11
                        assert all(not q for name, queues in self.queues.items() for q in queues), 'Completion passed owned data'
        assert self.accepted == self.delivered + self.discarded + sum(
            len(q) for queues in self.queues.values() for q in queues)
        return transfers


def capability_id(parameters):
    descriptor = b''.join(parameters[n].to_bytes(4, 'little') for n in DEFAULTS if n != 'TILE_ID')
    for name, count in (('INPUT_ELASTIC_MASK', 'DATA_INPUT_PORTS'),
                        ('OUTPUT_ELASTIC_MASK', 'DATA_OUTPUT_PORTS')):
        descriptor += parameters[name].to_bytes(4 * ((parameters[count] + 31) // 32), 'little')
    digest = 2166136261
    for byte in descriptor:
        digest = ((digest ^ byte) * 16777619) % (1 << 32)
    return digest % (1 << parameters['CAPABILITY_ID_WIDTH'])
