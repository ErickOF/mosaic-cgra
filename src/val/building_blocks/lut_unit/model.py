"""Integer numerical oracle and independent, deadline-based transaction ledgers."""
from collections import deque
from lut_unit.transaction import OUTPUTS


def number(raw):
    if isinstance(raw, int):
        return raw
    return int(raw, 2) if set(raw.lower()) <= {'0', '1'} else None


def pack(values, width):
    return sum(v << (n * width) for n, v in enumerate(values))


def hamming(width):
    count = 1
    while (1 << count) < width + count + 1:
        count += 1
    return count


def code_width(width, protection):
    if protection != 2:
        return width + protection
    return sum(bits + hamming(bits) + 1 for bits in chunks(width))


def chunks(width):
    return [min(256, width - offset) for offset in range(0, width, 256)]


def protected_read(value, mask, width, protection):
    """Independent extended-Hamming bit-position oracle for fault-injection masks."""
    if value is None:
        return 0, False, True
    if protection == 0:
        return value ^ mask, False, False
    if protection == 1:
        bad = bool(mask.bit_count() % 2)
        return value ^ (mask & ((1 << width) - 1)), False, bad
    result = 0
    corrected = bad = False
    corrected_stripes = 0
    offset = 0
    for stripe, bits in enumerate(chunks(width)):
        parity = hamming(bits)
        stored = bits + parity + 1
        part = (value >> (stripe * 256)) & ((1 << bits) - 1)
        word = 0
        data_index = 0
        for position in range(1, stored):
            if position & (position - 1):
                word |= ((part >> data_index) & 1) << (position - 1)
                data_index += 1
        for k in range(parity):
            bit = sum((word >> (p - 1)) & 1 for p in range(1, stored) if p & (1 << k)) % 2
            word |= bit << ((1 << k) - 1)
        word |= (word.bit_count() % 2) << (stored - 1)
        word ^= (mask >> offset) & ((1 << stored) - 1)
        syndrome = 0
        for position in range(1, stored):
            if (word >> (position - 1)) & 1:
                syndrome ^= position
        odd = bool(word.bit_count() % 2)
        if syndrome and not odd:
            bad = True
        elif odd:
            if syndrome >= stored:
                bad = True
            else:
                corrected = True
                corrected_stripes += 1
                if syndrome:
                    word ^= 1 << (syndrome - 1)
        decoded = 0
        data_index = 0
        for position in range(1, stored):
            if position & (position - 1):
                decoded |= ((word >> (position - 1)) & 1) << data_index
                data_index += 1
        result |= decoded << (stripe * 256)
        offset += stored
    bad |= corrected_stripes > 1
    return result, corrected and not bad, bad


def interpolate(y0, y1, fraction, c, signed, rounding):
    if signed:
        sign = 1 << (c.OUTPUT_WIDTH - 1)
        y0 = y0 - (1 << c.OUTPUT_WIDTH) if y0 & sign else y0
        y1 = y1 - (1 << c.OUTPUT_WIDTH) if y1 & sign else y1
    numerator = (y1 - y0) * fraction
    quotient, remainder = divmod(abs(numerator), 1 << c.INDEX_FRACTION_WIDTH)
    if rounding and (2 * remainder > (1 << c.INDEX_FRACTION_WIDTH) or
                     (2 * remainder == (1 << c.INDEX_FRACTION_WIDTH) and quotient % 2)):
        quotient += 1
    answer = y0 + (-quotient if numerator < 0 else quotient)
    answer = max(min(y0, y1), min(max(y0, y1), answer))
    return answer & ((1 << c.OUTPUT_WIDTH) - 1)


class LutModel:
    def __init__(self, c):
        self.c = c
        self.memory = [[None] * (1 << c.ADDRESS_WIDTH) for _ in range(c.NUM_BANKS)]
        self.masks = {}
        self.accounting = dict(lookups=0, results=0, discarded=0, programs=0, responses=0, program_discarded=0)
        self.reset()

    def reset(self):
        c = self.c
        if hasattr(self, 'pipe'):
            self.accounting['discarded'] += len(self.pipe) + len(self.results)
            self.accounting['program_discarded'] += len(self.programs)
        self.valid = [0] * c.NUM_BANKS
        self.versions = [0] * c.NUM_BANKS
        self.ids = [0] * c.NUM_BANKS
        self.quality = [0] * c.NUM_BANKS
        self.coverage = [set() for _ in range(c.NUM_BANKS)]
        self.faults = [False] * c.NUM_BANKS
        self.pipe = deque()
        self.results = deque()
        self.programs = deque()
        self.tick = self.error = self.hard = 0
        self.raw_fault = False
        self.events = {}

    def fault(self, fault):
        kind, bank, address, mask = fault
        if kind == 'table':
            self.masks[bank, address] = self.masks.get((bank, address), 0) ^ mask
        else:
            self.raw_fault = True

    def read(self, bank, address):
        return protected_read(self.memory[bank][address], self.masks.get((bank, address), 0),
                              self.c.OUTPUT_WIDTH, self.c.BUFFER_PROTECTION)

    def references(self, bank):
        return sum(row['bank'] == bank for row in self.results) + sum(row['bank'] == bank for row, _ in self.pipe)

    def complete(self, bank):
        return not self.c.TRACK_PROGRAM_COVERAGE or len(self.coverage[bank]) == 1 << self.c.ADDRESS_WIDTH

    @property
    def fatal(self):
        return bool(self.hard or any(self.faults))

    def lookup(self, v):
        c = self.c
        bank = v['i_lookup_bank']
        packet = dict.fromkeys(('data', 'version', 'table_id', 'quality_id', 'clipped_low',
                               'clipped_high', 'interpolated', 'predicated', 'error', 'error_code'), 0)
        packet.update(bank=bank, context_id=v['i_lookup_context_id'], tag=v['i_lookup_tag'])
        corrected = bad = access = False
        if bank >= c.NUM_BANKS:
            packet['error_code'] = 2
        else:
            packet.update(version=self.versions[bank], table_id=self.ids[bank], quality_id=self.quality[bank])
            if not self.valid[bank]:
                packet['error_code'] = 3
            elif v['i_lookup_interpolate'] and not c.SUPPORT_INTERPOLATION:
                packet['error_code'] = 4
            elif not v['i_lookup_predicate']:
                packet['predicated'] = 1
            else:
                access = True
                coordinate = v['i_lookup_coordinate']
                if v['i_lookup_index_signed'] and coordinate >> (c.ADDRESS_WIDTH + c.INDEX_FRACTION_WIDTH):
                    coordinate -= 1 << (1 + c.ADDRESS_WIDTH + c.INDEX_FRACTION_WIDTH)
                maximum = ((1 << c.ADDRESS_WIDTH) - 1) << c.INDEX_FRACTION_WIDTH
                packet['clipped_low'] = int(coordinate < 0)
                packet['clipped_high'] = int(coordinate > maximum)
                coordinate = min(max(coordinate, 0), maximum)
                address, fraction = divmod(coordinate, 1 << c.INDEX_FRACTION_WIDTH)
                y0, corrected, bad = self.read(bank, address)
                two = bool(v['i_lookup_interpolate'] and fraction and address < (1 << c.ADDRESS_WIDTH) - 1)
                packet['interpolated'] = int(two)
                answer = y0
                if two:
                    y1, upper_corrected, upper_bad = self.read(bank, address + 1)
                    corrected |= upper_corrected
                    bad |= upper_bad
                    answer = interpolate(y0, y1, fraction, c, v['i_lookup_output_signed'], v['i_lookup_round_mode'])
                packet['data'] = 0 if bad else answer
                if bad:
                    packet['error_code'] = 10
        packet['error'] = int(packet['error_code'] != 0)
        return packet, corrected, bad, access

    def program(self, v):
        c = self.c
        cmd, bank, address = (v['i_program_' + n] for n in ('command', 'bank', 'address'))
        packet = dict(command=cmd, bank=bank, address=address, read_data=0, version=0,
                      table_id=0, quality_id=0, bank_valid=0, error=0, error_code=0)
        corrected = bad = False
        if bank >= c.NUM_BANKS:
            packet['error_code'] = 2
        else:
            packet.update(version=self.versions[bank], table_id=self.ids[bank],
                          quality_id=self.quality[bank], bank_valid=self.valid[bank])
            error = 0
            if cmd == 0 and self.valid[bank]:
                error = 5
            elif cmd == 2:
                error = 10 if self.fatal else 8 if self.valid[bank] else 7 if self.references(bank) else 6 if not self.complete(bank) else 0
            elif cmd == 3:
                error = 8 if not self.valid[bank] else 7 if self.references(bank) else 0
            packet['error_code'] = error
            if not error:
                if cmd == 1:
                    data, corrected, bad = self.read(bank, address)
                    packet['read_data'] = 0 if bad else data
                    packet['error_code'] = 10 if bad else 0
                elif cmd == 2:
                    packet.update(version=(self.versions[bank] + 1) % (1 << c.TABLE_VERSION_WIDTH),
                        table_id=v['i_program_table_id'], quality_id=v['i_program_quality_id'], bank_valid=1)
                elif cmd == 3:
                    packet.update(table_id=0, quality_id=0, bank_valid=0)
        packet['error'] = int(packet['error_code'] != 0)
        return packet, corrected, bad

    def plan(self, p):
        v = {n: number(raw) for n, raw in p.items()}
        running = v['i_rstb'] == 1 and v['i_flush'] == 0
        healthy = not self.hard and not self.raw_fault
        empty = not self.pipe and not self.results
        result_pop = running and healthy and bool(self.results) and v['i_result_ready'] == 1
        program_pop = running and healthy and bool(self.programs) and v['i_program_response_ready'] == 1
        finish = bool(running and healthy and self.pipe and self.pipe[0][1] <= self.tick and
                      (len(self.results) < self.c.LOOKUP_RESPONSE_DEPTH or result_pop))
        fields = [v[n] for n in v if n.startswith('i_lookup_') and n not in ('i_lookup_valid', 'i_lookup_round_mode')]
        lookup_known = v['i_lookup_valid'] != 1 or (None not in fields and
                       (v['i_lookup_interpolate'] == 0 or v['i_lookup_round_mode'] is not None))
        program_known = v['i_program_valid'] != 1 or all(v[n] is not None for n in v
                        if n.startswith('i_program_') and n not in ('i_program_valid', 'i_program_response_ready'))
        candidate = running and healthy and program_known and (len(self.programs) < self.c.PROGRAM_RESPONSE_DEPTH or program_pop) and (v['i_drain'] == 0 or (v['i_drain'] == 1 and empty))
        exclusion = candidate and v['i_program_valid'] == 1 and v['i_program_command'] != 1 and v['i_program_bank'] == v['i_lookup_bank']
        lookup_ready = running and healthy and not self.fatal and v['i_drain'] == 0 and lookup_known and (len(self.pipe) < self.c.LOOKUP_PIPELINE_DEPTH or finish) and not exclusion
        take_lookup = lookup_ready and v['i_lookup_valid'] == 1
        lookup = self.lookup(v) if take_lookup else None
        conflict = take_lookup and lookup[3] and v['i_program_command'] == 1 and v['i_program_bank'] == v['i_lookup_bank']
        program_ready = candidate and not conflict
        take_program = program_ready and v['i_program_valid'] == 1
        program = self.program(v) if take_program else None
        return dict(v=v, running=running, healthy=healthy, empty=empty, idle=empty and not self.programs,
                    result_stall=running and healthy and bool(self.results) and v['i_result_ready'] == 0, finish=finish,
                    result_pop=result_pop, program_pop=program_pop, lookup_ready=lookup_ready,
                    program_ready=program_ready, lookup=lookup, program=program,
                    lookup_known=lookup_known, program_known=program_known)

    def outputs(self, p):
        a = self.plan(p)
        v, running, healthy = a['v'], a['running'], a['healthy']
        enabled = v['i_rstb'] == 1
        idle = a['empty'] and not self.programs
        o = dict.fromkeys(OUTPUTS, 0)
        o.update(o_lookup_ready=int(a['lookup_ready']), o_program_ready=int(a['program_ready']),
            o_result_valid=int(running and healthy and bool(self.results)),
            o_program_response_valid=int(running and healthy and bool(self.programs)),
            o_idle=int(running and healthy and idle),
            o_quiescent=int(running and healthy and idle and v['i_drain'] == 0 and
                           v['i_lookup_valid'] == 0 and v['i_program_valid'] == 0 and v['i_error_clear'] == 0),
            o_drain_done=int(running and healthy and v['i_drain'] == 1 and a['empty']),
            o_error=int(enabled and self.error != 0), o_error_code=self.error if enabled else 0,
            o_fatal_error=int(enabled and self.fatal))
        if enabled and healthy:
            o.update(o_bank_valid=pack(self.valid, 1), o_bank_version=pack(self.versions, self.c.TABLE_VERSION_WIDTH),
                o_bank_table_id=pack(self.ids, self.c.TABLE_ID_WIDTH), o_bank_quality_id=pack(self.quality, self.c.QUALITY_ID_WIDTH),
                o_bank_program_complete=pack([int(self.complete(b)) for b in range(self.c.NUM_BANKS)], 1),
                o_lookup_queue_occupancy=len(self.results), o_program_queue_occupancy=len(self.programs))
        if o['o_result_valid']:
            o.update({'o_result_' + ('table_version' if n == 'version' else n): value for n, value in self.results[0].items()})
        if o['o_program_response_valid']:
            o.update({'o_program_response_' + n: value for n, value in self.programs[0].items()})
        if enabled:
            o.update(self.events)
        return o

    def step(self, p):
        a = self.plan(p)
        v = a['v']
        if v['i_rstb'] == 0:
            self.reset()
            return
        if v['i_rstb'] != 1:
            return
        if v['i_flush'] == 1:
            self.events = {'o_flushed': int(not a['empty'])}
            self.accounting['discarded'] += len(self.pipe) + len(self.results)
            self.pipe.clear()
            self.results.clear()
            self.error = 11 if self.hard or self.raw_fault else 10 if any(self.faults) else 0
            self.tick += 1
            return
        if not a['running']:
            return
        events = {}
        error = 0
        if a['result_pop']:
            self.results.popleft()
            self.accounting['results'] += 1
        if a['program_pop']:
            self.programs.popleft()
            self.accounting['responses'] += 1
        if a['finish']:
            self.results.append(self.pipe.popleft()[0])
            events['o_event_lookup_complete'] = 1
        # Plans captured before any retiring item is removed: a lifecycle command
        # cannot invalidate the version observed by a same-edge retiring result.
        if a['program']:
            packet, corrected, bad = a['program']
            cmd, bank, address = (packet[n] for n in ('command', 'bank', 'address'))
            self.programs.append(packet)
            self.accounting['programs'] += 1
            if not packet['error']:
                events['o_event_program_' + ('write', 'read', 'commit', 'invalidate')[cmd]] = 1
                if cmd == 0:
                    self.memory[bank][address] = v['i_program_write_data']
                    self.masks[bank, address] = 0
                    self.coverage[bank].add(address)
                if cmd == 2:
                    self.valid[bank] = 1
                    self.versions[bank] = packet['version']
                    self.ids[bank] = packet['table_id']
                    self.quality[bank] = packet['quality_id']
                if cmd == 3:
                    self.valid[bank] = 0
                    self.ids[bank] = self.quality[bank] = 0
                    self.coverage[bank].clear()
                    self.faults[bank] = False
            elif cmd == 1 and bad:
                events['o_event_program_read'] = 1
            error = packet['error_code']
            if corrected:
                error = 9
                events['o_event_table_corrected'] = 1
            if bad:
                events['o_event_table_uncorrectable'] = 1
                if self.valid[bank]:
                    self.faults[bank] = True
        if a['lookup']:
            packet, corrected, bad, access = a['lookup']
            self.pipe.append((packet, self.tick + self.c.LOOKUP_PIPELINE_DEPTH))
            self.accounting['lookups'] += 1
            events['o_event_lookup_accept'] = 1
            for n in ('clipped_low', 'clipped_high', 'interpolated'):
                events['o_event_' + {'clipped_low': 'clip_low', 'clipped_high': 'clip_high', 'interpolated': 'interpolate'}[n]] = packet[n]
            if packet['error'] and not error:
                error = packet['error_code']
            if corrected:
                error = 9
                events['o_event_table_corrected'] = 1
            if bad:
                error = 10
                events['o_event_table_uncorrectable'] = 1
                self.faults[packet['bank']] = True
        if v['i_lookup_valid'] == 1 and not a['lookup_ready']:
            events['o_event_lookup_stall'] = 1
        events['o_event_result_stall'] = int(a['result_stall'])
        if any(item and item[2] for item in (a['lookup'], a['program'])):
            error = 10
        controls = ('i_rstb', 'i_flush', 'i_drain', 'i_lookup_valid', 'i_result_ready', 'i_program_valid', 'i_program_response_ready', 'i_error_clear')
        if any(v[n] is None for n in controls) or not a['lookup_known'] or not a['program_known']:
            error = 1
        if self.raw_fault:
            self.hard = 1
            error = 11
        clear = (a['idle'] and v['i_drain'] == 0 and v['i_lookup_valid'] == 0 and
                 v['i_program_valid'] == 0 and v['i_error_clear'] == 1)
        if clear:
            self.error = 11 if self.hard or self.raw_fault else 10 if any(self.faults) else 0
        elif not self.error:
            self.error = error
        self.events = events
        self.tick += 1
