"""Independent integer equations and elastic histories; no private RTL prediction.

Endpoints and log2(e) are computed directly by pinned MPFR at 512 bits. They do
not read the RTL master image, generator functions, or generated table literals.
"""
from functools import lru_cache
import zlib
import gmpy2 as g
from exp_unit.transaction import INPUTS, OUTPUTS, REQUEST


def number(raw):
    if isinstance(raw, int):
        return raw
    return int(raw, 2) if set(raw.lower()) <= {'0', '1'} else None


def rounded(numerator, denominator, even):
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    increment = even and (2 * remainder > denominator or
                          2 * remainder == denominator and quotient % 2)
    return sign * (quotient + int(bool(increment))), bool(remainder)


def direct_integer(value):
    n, d = value.as_integer_ratio()
    return rounded(int(n), int(d), True)[0]


@lru_cache(maxsize=None)
def image(address, fraction):
    with g.context(precision=512, round=g.RoundToNearest):
        return tuple(direct_integer(g.exp2(g.mpfr(i) / (1 << address)) * (1 << fraction))
                     for i in range((1 << address) + 1))


@lru_cache(maxsize=None)
def log2e(fraction):
    with g.context(precision=512, round=g.RoundToNearest):
        return direct_integer(g.mpfr(1 << fraction) / g.log(g.mpfr(2)))


_IDENTITIES = {}

def identities(c):
    key = tuple(c.parameters.items())
    if key in _IDENTITIES:
        result, quality = _IDENTITIES[key]
        return result.copy(), quality
    table = image(c.TABLE_ADDRESS_WIDTH, c.INTERNAL_FRACTION_WIDTH)
    crc = zlib.crc32(b''.join(n.to_bytes((c.INTERNAL_WIDTH + 7) // 8, 'little') for n in table))
    const_crc = zlib.crc32(log2e(c.LOG2E_FRACTION_WIDTH).to_bytes(
        (c.LOG2E_FRACTION_WIDTH + 9) // 8, 'little'))
    names = ('INPUT_WIDTH', 'INPUT_FRACTION_WIDTH', 'RANGE_WIDTH', 'RANGE_FRACTION_WIDTH',
             'LOG2E_FRACTION_WIDTH', 'INTERNAL_WIDTH', 'INTERNAL_FRACTION_WIDTH',
             'OUTPUT_WIDTH', 'OUTPUT_FRACTION_WIDTH', 'TABLE_ADDRESS_WIDTH')
    quality = zlib.crc32(b''.join(c.parameters[n].to_bytes(4, 'little') for n in reversed(names)))
    result = dict(o_table_checksum=crc, o_table_image_id=crc ^ 0x45585001,
                o_log2e_checksum=const_crc, o_log2e_constant_id=const_crc ^ 0x4c324501)
    quality &= 0xfffffff0
    _IDENTITIES[key] = result.copy(), quality
    return result, quality


def predict(c, p):
    result = dict.fromkeys((n for n in OUTPUTS if n.startswith('o_result_') and n != 'o_result_valid'), 0)
    base, interpolation, mode, signed = (p['i_request_' + n] for n in
                                       ('base', 'interpolate', 'round_mode', 'output_signed'))
    result.update(o_result_base=base, o_result_output_signed=signed,
                  o_result_context_id=p['i_request_context_id'], o_result_tag=p['i_request_tag'])
    error = 1 if (base == 0 and not c.SUPPORT_EXP_E or base == 1 and not c.SUPPORT_EXP2) else \
        2 if interpolation and not c.SUPPORT_INTERPOLATION else 0
    fact = dict(active=False, base=base, interpolation=interpolation, mode=mode, signed=signed,
                error=error, k=0, address=0, remainder=0)
    if error:
        result.update(o_result_error=1, o_result_error_code=error)
        return result, fact
    if not p['i_request_predicate']:
        result['o_result_predicated'] = 1
        return result, fact
    x = p['i_request_operand']
    if x & (1 << (c.INPUT_WIDTH - 1)):
        x -= 1 << c.INPUT_WIDTH
    numerator = x if base else x * log2e(c.LOG2E_FRACTION_WIDTH)
    shift = c.RANGE_FRACTION_WIDTH - c.INPUT_FRACTION_WIDTH - (0 if base else c.LOG2E_FRACTION_WIDTH)
    z, lost_conversion = (numerator << shift, False) if shift >= 0 else rounded(numerator, 1 << -shift, mode)
    k, fraction = divmod(z, 1 << c.RANGE_FRACTION_WIDTH)
    remainder_width = c.RANGE_FRACTION_WIDTH - c.TABLE_ADDRESS_WIDTH
    address, remainder = divmod(fraction, 1 << remainder_width)
    table = image(c.TABLE_ADDRESS_WIDTH, c.INTERNAL_FRACTION_WIDTH)
    mantissa = table[address]
    lost_interpolation = False
    if interpolation:
        delta, lost_interpolation = rounded((table[address + 1] - table[address]) * remainder,
                                            1 << remainder_width, mode)
        mantissa += delta
    net_shift = c.OUTPUT_FRACTION_WIDTH - c.INTERNAL_FRACTION_WIDTH + k
    maximum = (1 << (c.OUTPUT_WIDTH - signed)) - 1
    overflow = False
    lost_output = False
    if net_shift >= 0:
        overflow = net_shift >= c.OUTPUT_WIDTH or (mantissa << net_shift) > maximum
        value = maximum if overflow else mantissa << net_shift
    elif -net_shift > c.INTERNAL_WIDTH + 1:
        value, lost_output = 0, True
    else:
        denominator = 1 << -net_shift
        overflow = mantissa > maximum * denominator
        value, lost_output = rounded(mantissa, denominator, mode)
        if overflow:
            value = maximum
    _, quality = identities(c)
    result.update(o_result_data=value, o_result_reduced_exponent=k % (1 << (c.RANGE_WIDTH - c.RANGE_FRACTION_WIDTH)),
                  o_result_interpolated=interpolation, o_result_quality_id=quality | base << 3 |
                  interpolation << 2 | mode << 1 | signed, o_result_overflow=int(overflow),
                  o_result_saturated=int(overflow), o_result_underflow=int(value == 0),
                  o_result_rounded=int(lost_conversion or lost_interpolation or lost_output),
                  o_result_approximate=1)
    fact.update(active=True, x=x, z=z, k=k, address=address, remainder=remainder,
                mantissa=mantissa, net_shift=net_shift, lost_conversion=lost_conversion,
                lost_interpolation=lost_interpolation, lost_output=lost_output)
    return result, fact


EVENTS = ('request_accept', 'result_complete', 'request_stall', 'result_stall', 'base_e',
          'base_2', 'table_lookup', 'interpolation', 'overflow', 'underflow',
          'table_corrected', 'table_uncorrectable')


class ExpUnitModel:
    def __init__(self, c):
        self.c = c
        self.accepted = self.delivered = self.discarded = 0
        self.fault = None
        self.reset(False)

    def reset(self, account=True):
        if account:
            self.discarded += self.occupancy
        self.pipeline = [None] * self.c.PIPELINE_DEPTH
        self.queue = []
        self.error = self.fatal = 0
        self.pulses = dict.fromkeys(('o_event_' + n for n in EVENTS), 0)
        self.pulses['o_flushed'] = 0
        self.initialized = True

    @property
    def occupancy(self):
        return sum(token is not None for token in self.pipeline) + len(self.queue)

    def evaluate(self, raw):
        c = self.c
        p = {n: number(raw[n]) for n in INPUTS}
        controls = all(p[n] is not None for n in
            ('i_rstb', 'i_drain', 'i_flush', 'i_error_clear', 'i_request_valid', 'i_result_ready'))
        fields = all(p[n] is not None for n in REQUEST)
        permit = controls and p['i_rstb'] == 1 and p['i_flush'] == 0 and not self.fatal
        corrected = False
        fault = 0
        if self.fault:
            kind, index, mask = self.fault
            if kind == 'identity':
                fault = 7
            elif kind == 'stage' and self.pipeline[index] is not None:
                fault = 8
            elif kind == 'owner':
                fault = 8
            elif kind == 'rom' and permit and self.pipeline[1] and self.pipeline[1][1]['active']:
                fact = self.pipeline[1][1]
                selected = index == fact['address'] or fact['interpolation'] and index == fact['address'] + 1
                if selected:
                    if c.TABLE_PROTECTION == 2 and mask.bit_count() == 1:
                        corrected = True
                    else:
                        fault = 5
        if p['i_rstb'] != 1:
            fault = 0
        run = permit and not fault
        out = dict.fromkeys(OUTPUTS, 0)
        out.update(self.pulses)
        ids, _ = identities(c)
        if self.fault and self.fault[0] == 'identity':
            ids['o_table_image_id'] ^= self.fault[2]
        out.update(ids, o_error=int(bool(self.error)), o_error_code=self.error,
                   o_fatal_error=self.fatal, o_busy=int(bool(self.occupancy or self.fatal or fault)),
                   o_idle=int(not (self.occupancy or self.fatal or fault)), o_output_queue_occupancy=len(self.queue))
        out['o_quiescent'] = int(out['o_idle'] and controls and p['i_rstb'] == 1 and
            p['i_flush'] == p['i_drain'] == p['i_request_valid'] == p['i_error_clear'] == 0)
        out['o_drain_done'] = int(controls and p['i_flush'] == 0 and p['i_rstb'] == p['i_drain'] == 1 and out['o_idle'])
        if run and self.queue:
            out.update(self.queue[0][0], o_result_valid=1)
        space = len(self.queue) < c.OUTPUT_QUEUE_DEPTH or run and p['i_result_ready'] == 1 and bool(self.queue)
        ready = [False] * c.PIPELINE_DEPTH
        for index in reversed(range(c.PIPELINE_DEPTH)):
            ready[index] = self.pipeline[index] is None or run and space
            space = ready[index]
        out['o_request_ready'] = int(run and not p['i_drain'] and fields and ready[0])
        plan = dict(p=p,run=run,permit=permit,ready=ready,fault=fault,corrected=corrected,
                    accept=p['i_request_valid'] == 1 and bool(out['o_request_ready']),
                    pop=out['o_result_valid'] == 1 and p['i_result_ready'] == 1,
                    create=run and self.pipeline[-1] is not None and (len(self.queue) < c.OUTPUT_QUEUE_DEPTH or
                           out['o_result_valid'] == 1 and p['i_result_ready'] == 1),
                    flush=p['i_rstb'] == p['i_flush'] == 1,
                    unknown=p['i_rstb'] != 0 and (not controls or p['i_request_valid'] == 1 and not fields))
        return out, plan

    def step(self, raw, edge):
        p = {n: number(raw[n]) for n in INPUTS}
        if p['i_rstb'] == 0 and (edge or self.c.ASYNC_RESET):
            self.reset()
            return {'reset'}
        if not edge:
            return set()
        before, plan = self.evaluate(raw)
        old = list(self.pipeline)
        events = set()
        self.pulses = dict.fromkeys(self.pulses, 0)
        def pulse(name):
            self.pulses['o_event_' + name] = 1
            events.add(name)
        if plan['fault']:
            self.fatal, self.error = 1, plan['fault']
        elif not self.fatal:
            if plan['flush'] or (before['o_idle'] and p['i_error_clear'] == 1 and
                not p['i_request_valid'] and not p['i_drain'] and not plan['unknown']):
                self.error = 0
            elif not self.error:
                if plan['unknown']:
                    self.error = 3
                elif plan['run'] and old[1] and plan['ready'][2] and plan['corrected']:
                    self.error = 4
                elif plan['accept']:
                    self.error = predict(self.c, p)[1]['error']
        if plan['permit'] and plan['fault'] == 5:
            pulse('table_uncorrectable')
        if p['i_rstb'] == 1 and p['i_request_valid'] == 1 and not before['o_request_ready']:
            pulse('request_stall')
        if before['o_result_valid'] and p['i_result_ready'] == 0:
            pulse('result_stall')
        if plan['flush']:
            live = self.occupancy
            self.discarded += live
            self.pipeline = [None] * self.c.PIPELINE_DEPTH
            self.queue.clear()
            self.pulses['o_flushed'] = int(live > 0)
            events.add('flush')
            return events
        if not plan['run']:
            return events
        if plan['pop']:
            self.queue.pop(0)
            self.delivered += 1
            events.add('delivered')
        if plan['create']:
            self.queue.append(old[-1])
            pulse('result_complete')
            r, fact = old[-1]
            if r['o_result_overflow']:
                pulse('overflow')
            if r['o_result_underflow']:
                pulse('underflow')
        for index in (2, 3):
            if old[index - 1] and plan['ready'][index] and old[index - 1][1]['active']:
                if index == 2:
                    pulse('table_lookup')
                    if plan['corrected']:
                        pulse('table_corrected')
                elif old[index - 1][1]['interpolation']:
                    pulse('interpolation')
        for index in reversed(range(len(old))):
            if plan['ready'][index]:
                self.pipeline[index] = old[index - 1] if index else None
        if plan['accept']:
            self.pipeline[0] = predict(self.c, p)
            self.accepted += 1
            pulse('request_accept')
            fact = self.pipeline[0][1]
            if fact['active']:
                pulse('base_2' if fact['base'] else 'base_e')
        assert self.accepted == self.delivered + self.discarded + self.occupancy
        return events
