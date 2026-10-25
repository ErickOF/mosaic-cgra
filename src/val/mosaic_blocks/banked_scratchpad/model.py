"""Independent byte memory, mapping, region comparison, and protection oracle."""
from banked_scratchpad.config import descriptor_fields, dimensions


def lane(value, width, index):
    return value >> (width * index) & ((1 << width) - 1)


def number(value):
    text = str(value)
    return None if any(c in text.lower() for c in 'xz') else int(value)


def map_address(p, address):
    stripe, offset = divmod(address, p['INTERLEAVE_BYTES'])
    row, bank = divmod(stripe, p['NUM_BANKS'])
    if p['MAP_MODE']:
        bank ^= row % p['NUM_BANKS']
    return bank, row * p['INTERLEAVE_BYTES'] + offset


def encode_descriptor(a, d):
    value = 0
    for name, width in descriptor_fields(a):
        value = value << width | d[name]
    return value


def empty_descriptor(a):
    return {name: 0 for name, _ in descriptor_fields(a)}


def class_allowed(state, client):
    return state == 1 and client == 0 or state == 2 and client == 1 or \
        state == 3 and client >= 2 or state in (4, 5)


class Architecture:
    def __init__(self, p):
        self.p, self.a = p, dimensions(p)
        self.memory = {}
        self.faults = {}
        self.reset()

    def reset(self):
        self.regions = [empty_descriptor(self.a) for _ in range(self.a['R'])]
        self.power = [0] * self.a['B']
        self.destroyed = [False] * self.a['B']

    def command(self, x):
        """Return expected descriptor, error and atomic replacements without mutation."""
        a, p = self.a, self.p
        r, s, op = x['cmd_a'], x['cmd_b'], x['cmd_opcode']
        old = self.regions[r].copy() if r < a['R'] else empty_descriptor(a)
        other = self.regions[s].copy() if s < a['R'] else empty_descriptor(a)
        new, updates, code = old.copy(), {}, 0
        if any(v is None for v in x.values()):
            return old, 1, {}
        if r >= a['R']:
            return old, 2, {}
        if op > 4:
            return old, 3, {}
        if op == 0:
            return old, 0, {}
        if op == 1:
            if old['valid']:
                code = 6
            elif not (x['base'] < x['limit'] <= a['capacity'] and
                x['base'] % p['INTERLEAVE_BYTES'] == x['limit'] % p['INTERLEAVE_BYTES'] == 0):
                code = 4
            elif any(d['valid'] and x['base'] < d['limit'] and x['limit'] > d['base']
                for d in self.regions):
                code = 5
            else:
                new = empty_descriptor(a) | dict(valid=1, base=x['base'], limit=x['limit'],
                    owner=x['owner_id'], kernel=x['kernel_id'], state=x['state'],
                    contents=x['contents_valid'], read_mask=x['read_mask'],
                    write_mask=x['write_mask'], group_id=x['buffer_group'],
                    role=x['buffer_role'], generation=old['generation'] % ((1 << a['G']) - 1) + 1)
        elif not old['valid']:
            code = 6
        elif (old['generation'], old['state']) != (x['expected_generation_a'], x['expected_state_a']):
            code = 7
        elif op != 4 and old['generation'] == (1 << a['G']) - 1:
            code = 8
        elif op == 4:
            new.update(valid=0, contents=0)
        elif op == 2:
            new.update(owner=x['owner_id'], kernel=x['kernel_id'], state=x['state'],
                contents=x['contents_valid'], read_mask=x['read_mask'], write_mask=x['write_mask'],
                generation=old['generation'] + 1)
        elif op == 3:
            if not p['SUPPORT_DOUBLE_BUFFER'] or s >= a['R'] or r == s or not other['valid'] or \
                old['group_id'] == 0 or old['group_id'] != other['group_id'] or \
                old['limit'] - old['base'] != other['limit'] - other['base'] or \
                {old['role'], other['role']} != {1, 2}:
                code = 9
            elif (other['generation'], other['state']) != (x['expected_generation_b'], x['expected_state_b']):
                code = 7
            elif other['generation'] == (1 << a['G']) - 1:
                code = 8
            elif not (old if old['role'] == 2 else other)['contents']:
                code = 10
            else:
                fields = ('owner', 'kernel', 'state', 'contents', 'read_mask', 'write_mask', 'role')
                new.update({k: other[k] for k in fields})
                new['generation'] += 1
                updates[s] = other | {k: old[k] for k in fields} | dict(
                    generation=other['generation'] + 1)
        if not code and op != 4:
            if new['state'] > 5 or new['role'] > 2 or \
                (new['group_id'] == 0) != (new['role'] == 0) or \
                not p['SUPPORT_DOUBLE_BUFFER'] and new['role']:
                code = 11
            elif any(self.power[b] != 0 for d in (new, *updates.values())
                for b in self.banks_for_region(d)):
                code = 12
        if code:
            return old, code, {}
        updates[r] = new
        return new, 0, updates

    def banks_for_region(self, d):
        return {map_address(self.p, addr)[0] for addr in
            range(d['base'], d['limit'], self.p['INTERLEAVE_BYTES'])} if d['valid'] else set()

    def check(self, c, x):
        p, a = self.p, self.a
        if any(x[k] is None for k in ('opcode', 'tag', 'region_id', 'generation')):
            return 1
        if x['opcode'] > 2:
            return 11
        if x['opcode'] == 2:
            return 0
        if any(x[k] is None for k in ('addr', 'size', 'owner_id', 'kernel_id')) or \
            x['opcode'] == 1 and x['wstrb'] is None:
            return 1
        addr, size = x['addr'], x['size']
        if addr >= a['capacity'] or addr + size > a['capacity']:
            return 2
        if not 0 < size <= a['Y'] or size & (size - 1):
            return 3
        if addr % a['Y'] + size > a['Y'] or addr % p['INTERLEAVE_BYTES'] + size > p['INTERLEAVE_BYTES']:
            return 5
        if addr % size:
            return 4
        if x['opcode'] == 1 and x['wstrb'] != ((1 << size) - 1) << (addr % a['Y']):
            return 6
        bank, _ = map_address(p, addr)
        if p['ENFORCE_REGIONS']:
            matches = [r for r, d in enumerate(self.regions) if d['valid'] and d['base'] <= addr < d['limit']]
            if matches != [x['region_id']] or addr + size > self.regions[matches[0]]['limit']:
                return 12
            d = self.regions[matches[0]]
            if d['generation'] != x['generation']:
                return 13
            if d['state'] != 4 and (d['owner'], d['kernel']) != (x['owner_id'], x['kernel_id']):
                return 14
            if not class_allowed(d['state'], c) or \
                not (d['read_mask'] if x['opcode'] == 0 else d['write_mask']) >> c & 1 or \
                x['opcode'] == 1 and d['state'] == 4:
                return 10
            if x['opcode'] == 0 and not d['contents']:
                return 15
        if self.power[bank] != 0:
            return 16
        if x['opcode'] == 0 and self.destroyed[bank]:
            return 15
        return 0

    def access(self, x):
        """Apply bank-accepted order; protected RMW preserves/repairs untouched bytes."""
        a, p = self.a, self.p
        addr, size = x['addr'], x['size']
        base = addr // a['Y'] * a['Y']
        bank, local = map_address(p, base)
        key = bank, local // a['Y']
        bits = self.faults.get(key, 0)
        detects = bool(bits and (x['opcode'] == 0 or size != a['Y']))
        if p['PROTECTION_MODE'] == 1:
            granule = p['PARITY_GRANULARITY'] // 8
            offset = addr - base
            detects = False
            for g in range(a['Y'] // granule):
                start, end = g * granule, (g + 1) * granule
                intersects = start < offset + size and end > offset
                partial = not (offset <= start and offset + size >= end)
                group_bits = bits >> (8 * start) & ((1 << (8 * granule)) - 1)
                syndrome = group_bits.bit_count() % 2 ^ (bits >> (a['D'] + g) & 1)
                if intersects and syndrome and (x['opcode'] == 0 or partial):
                    detects = True
        corrected = int(detects and p['PROTECTION_MODE'] == 2 and bits.bit_count() == 1)
        bad = detects and (p['PROTECTION_MODE'] == 1 or bits.bit_count() > 1)
        if bad:
            return 0, 7 if p['PROTECTION_MODE'] == 1 else 8, 0, 1
        if corrected:
            if p['SCRUB_ON_CORRECT'] or x['opcode'] == 1:
                self.faults.pop(key, None)
        if x['opcode'] == 1:
            for i in range(size):
                self.memory[addr + i] = x['wdata'] >> (8 * i) & 255
            if p['PROTECTION_MODE'] == 1:
                overwritten = ((1 << (8 * size)) - 1) << (8 * (addr - base))
                for g in range(a['Y'] // granule):
                    if g * granule < addr - base + size and (g + 1) * granule > addr - base:
                        overwritten |= 1 << (a['D'] + g)
                remaining = bits & ~overwritten
                if remaining:
                    self.faults[key] = remaining
                else:
                    self.faults.pop(key, None)
            else:
                self.faults.pop(key, None)
            return 0, 0, corrected, 0
        value = sum(self.memory[addr + i] << (8 * i) for i in range(size))
        if bits and p['PROTECTION_MODE'] != 2:
            value ^= bits >> (8 * (addr - base)) & ((1 << (8 * size)) - 1)
        return value, 0, corrected, 0
