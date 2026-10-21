"""Unbounded integer descriptor model using base + row*stride + column*step.

The reference never predicts addresses by adding to the previous RTL address.
This detects row-origin errors, signed coercion, and silent address wrapping.
"""

from enum import IntEnum
from mosaic_uvm.logic import bits
from agu.transaction import DESCRIPTOR, OUTPUTS


class Mode(IntEnum):
    LINEAR = 0
    STRIDED = 1
    TWO_D = 2


class Error(IntEnum):
    NONE=0; MODE=1; INNER_COUNT=2; OUTER_COUNT=3; OUTER_1D=4; SIZE=5
    BASE_ALIGN=6; INNER_ALIGN=7; OUTER_ALIGN=8; UNKNOWN=9; UNDERFLOW=10; OVERFLOW=11


def known(word):
    return set(word) <= {'0','1'}


def signed(word):
    value = int(word,2)
    return value-(1 << len(word)) if word[0] == '1' else value


def descriptor_error(c, p):
    if not known(p['i_mode']) or int(p['i_mode'],2) == 3:
        return Error.MODE
    mode = int(p['i_mode'],2)
    required = set(DESCRIPTOR)-{'i_inner_stride','i_outer_stride'}
    if mode != Mode.LINEAR: required.add('i_inner_stride')
    if mode == Mode.TWO_D: required.add('i_outer_stride')
    if not all(known(p[name]) for name in required): return Error.UNKNOWN
    d = {name:int(p[name],2) for name in required}
    if d['i_inner_count'] == 0: return Error.INNER_COUNT
    if d['i_outer_count'] == 0: return Error.OUTER_COUNT
    if mode != Mode.TWO_D and d['i_outer_count'] != 1: return Error.OUTER_1D
    size = d['i_element_size_log2']
    if size > c.max_log2: return Error.SIZE
    alignment = 1 << size
    if d['i_base_address'] % alignment: return Error.BASE_ALIGN
    if mode != Mode.LINEAR and signed(p['i_inner_stride']) % alignment: return Error.INNER_ALIGN
    if mode == Mode.TWO_D and signed(p['i_outer_stride']) % alignment: return Error.OUTER_ALIGN
    return Error.NONE


class AguModel:
    def __init__(self, config):
        self.c = config
        self.initialized = False
        self.reset()
        self.initialized = False

    def reset(self):
        self.active, self.error, self.accepted = False, Error.NONE, 0
        self.started = self.transferred = self.completed = 0
        self.d, self.position = {}, 0
        self.initialized = True

    def location(self, position=None):
        d = self.d
        row, column = divmod(self.position if position is None else position,d['i_inner_count'])
        address = d['i_base_address'] + row*d['outer_step'] + column*d['inner_step']
        return row,column,address

    def outputs(self,p):
        c = self.c
        values = dict.fromkeys(OUTPUTS,0)
        values.update(o_config_ready=int(not self.active and not self.error
                and p['i_rstb']=='1' and p['i_error_clear']=='0'),
            o_idle=int(not self.active and not self.error), o_valid=int(self.active), o_active=int(self.active),
            o_descriptor_started=self.started, o_address_accepted=self.transferred, o_completed=self.completed,
            o_addresses_accepted=self.accepted, o_error=int(bool(self.error)), o_error_code=int(self.error))
        if self.active:
            d = self.d
            row,column,address = self.location()
            last = self.position == d['i_inner_count']*d['i_outer_count']-1
            values.update(o_address=address, o_inner_index=column, o_outer_index=row,
                o_first=int(self.position==0), o_last=int(last), o_row_first=int(column==0),
                o_row_last=int(column==d['i_inner_count']-1),
                o_end_of_stream=int(last and d['i_emit_end_of_stream']))
            values.update({'o_'+name[2:]:d[name] for name in ('i_element_size_log2','i_is_write',
                'i_address_space','i_channel_id','i_context_id')})
        return {name:bits(value,c.widths[name]) for name,value in values.items()}

    def step(self,p):
        before = 'active' if self.active else 'error' if self.error else 'idle'
        event = dict(kind='idle', before=before, error=0, previous_error=int(self.error))
        self.started = self.transferred = self.completed = 0
        if p['i_rstb']=='0':
            self.reset()
            return event | dict(kind='reset')
        if not self.active and p['i_error_clear']=='1':
            self.error, self.accepted = Error.NONE, 0
            return event | dict(kind='clear')
        if self.outputs(p)['o_config_ready']=='1' and p['i_config_valid']=='1':
            self.accepted = 0
            self.error = descriptor_error(self.c,p)
            if self.error:
                return event | dict(kind='reject',error=int(self.error))
            self.d = {name:int(value,2) for name,value in p.items() if name in DESCRIPTOR and known(value)}
            self.d['inner_step'] = 1 << self.d['i_element_size_log2'] if self.d['i_mode']==Mode.LINEAR else signed(p['i_inner_stride'])
            self.d['outer_step'] = signed(p['i_outer_stride']) if self.d['i_mode']==Mode.TWO_D else 0
            self.active, self.position, self.started = True,0,1
            return event | dict(kind='start',descriptor=self.d.copy())
        if self.active:
            if p['i_ready']!='1': return event | dict(kind='stall',unknown=not known(p['i_ready']))
            row,column,address = self.location()
            event.update(descriptor=self.d.copy(),row=row,column=column,address=address)
            self.accepted += 1
            self.transferred = 1
            if self.accepted == self.d['i_inner_count']*self.d['i_outer_count']:
                self.active, self.completed = False,1
                return event | dict(kind='complete')
            successor = self.location(self.position+1)[2]
            if successor < 0 or successor > self.c.mask:
                self.active = False
                self.error = Error.UNDERFLOW if successor < 0 else Error.OVERFLOW
                return event | dict(kind='range',error=int(self.error),position=self.position)
            self.position += 1
            return event | dict(kind='accept')
        return event
