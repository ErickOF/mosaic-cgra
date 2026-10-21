"""Independent arbitrary-precision per-lane state and numerical range oracle."""

from enum import IntEnum
from mosaic_uvm.logic import bits
from accumulator.transaction import RESPONSE


class Command(IntEnum):
    CLEAR = 0
    LOAD = 1
    ADD = 2
    SUB = 3


def known(word):
    return set(word) <= {'0', '1'}


def lane(word, index, width):
    end = len(word)-index*width
    return word[end-width:end]


def signed_value(value, width):
    return value-(1 << width) if value & (1 << (width-1)) else value


def calculate(width, command, left, right, signed, saturate):
    """Use mathematical range tests, not RTL carry or sign-bit equations."""
    modulus = 1 << width
    low, high = (-(modulus//2), modulus//2-1) if signed else (0, modulus-1)
    a, b = (signed_value(left, width), signed_value(right, width)) if signed else (left, right)
    mathematical = 0 if command == Command.CLEAR else b if command == Command.LOAD else a+b if command == Command.ADD else a-b
    arithmetic = command in (Command.ADD, Command.SUB)
    wrapped = mathematical % modulus
    final = min(high, max(low, mathematical)) % modulus if arithmetic and saturate else wrapped
    status = dict(carry=int(arithmetic and not signed and command == Command.ADD and mathematical > high),
        borrow=int(arithmetic and not signed and command == Command.SUB and mathematical < 0),
        overflow=int(arithmetic and signed and not low <= mathematical <= high),
        saturated=int(arithmetic and saturate and final != wrapped), zero=int(final == 0),
        negative=int(signed and final >= modulus//2))
    return final, status, mathematical


class AccumulatorModel:
    def __init__(self, config):
        self.config = config
        self.values = [None]*config.lanes
        self.kinds = [None]*config.lanes
        self.response = {name:'0'*config.widths[name] for name in RESPONSE}
        self.raw = {}
        self.initialized = False
        self.accepted = self.legal = self.illegal = self.bubbles = self.stalls = self.edges = 0
        self.updates = [0]*config.lanes

    def reset(self):
        self.values = [None]*self.config.lanes
        self.kinds = [None]*self.config.lanes
        self.response = {name:'0'*self.config.widths[name] for name in RESPONSE}
        self.initialized = True

    def causes(self, ports):
        c, causes = self.config, set()
        fields = dict(i_command='unknown_command', i_lane_mask='unknown_mask',
            i_signed='unknown_signed', i_saturate='unknown_saturate')
        for field, cause in fields.items():
            if not known(ports[field]):
                causes.add(cause)
        command = int(ports['i_command'], 2) if known(ports['i_command']) else None
        if command == Command.SUB and not c.subtract:
            causes.add('unsupported_subtract')
        if ports['i_saturate'] == '1':
            if not c.saturation:
                causes.add('unsupported_saturation')
            if command in (Command.CLEAR, Command.LOAD):
                causes.add('nonarithmetic_saturation')
        if command in (Command.ADD, Command.SUB):
            for k, bit in enumerate(reversed(ports['i_lane_mask'])):
                if bit == '1':
                    if self.values[k] is None:
                        causes.add('invalid_state')
                    elif known(ports['i_signed']) and self.kinds[k] != int(ports['i_signed']):
                        causes.add('signedness_mismatch')
        return causes

    def selected(self, ports):
        if (ports['i_rstb'] != '1' or ports['i_clock_enable'] != '1' or ports['i_valid'] != '1'
                or self.causes(ports)):
            return set()
        return {k for k, bit in enumerate(reversed(ports['i_lane_mask'])) if bit == '1'}

    def outputs(self):
        c = self.config
        return self.response | dict(o_data=''.join(bits(value or 0, c.width) for value in reversed(self.values)),
            o_state_valid=''.join(str(int(value is not None)) for value in reversed(self.values)),
            o_state_signed=''.join(str(kind or 0) for kind in reversed(self.kinds)))

    def step(self, ports):
        c = self.config
        self.edges += 1
        before, kinds = tuple(self.values), tuple(self.kinds)
        event = dict(before=before, kinds=kinds, accepted=False, selected=set(), causes=set(), numeric=[])
        if ports['i_rstb'] == '0':
            self.reset()
            return event | dict(operation='reset')
        if ports['i_clock_enable'] == '0':
            self.stalls += 1
            return event | dict(operation='stall')
        self.response = {name:'0'*c.widths[name] for name in RESPONSE}
        if ports['i_valid'] == '0':
            self.bubbles += 1
            return event | dict(operation='bubble')
        self.accepted += 1
        event['accepted'] = True
        event['causes'] = self.causes(ports)
        self.response['o_valid'] = '1'
        if event['causes']:
            self.illegal += 1
            self.response['o_illegal_operation'] = '1'
        else:
            self.legal += 1
            event['selected'] = self.selected(ports)
            command, signed, saturate = (int(ports[name], 2) for name in ('i_command', 'i_signed', 'i_saturate'))
            packed = {name:0 for name in RESPONSE if name not in ('o_valid', 'o_illegal_operation')}
            for k in event['selected']:
                previous = self.values[k]
                incoming = 0 if command == Command.CLEAR else int(lane(ports['i_data'], k, c.width), 2)
                result, status, mathematical = calculate(c.width, command, previous or 0, incoming, signed, saturate)
                self.values[k] = result
                if command in (Command.CLEAR, Command.LOAD):
                    self.kinds[k] = signed
                self.updates[k] += 1
                packed['o_updated_mask'] |= 1 << k
                for name, value in status.items():
                    packed['o_' + name] |= value << k
                event['numeric'].append((k, command, signed, saturate, previous, incoming, result, status, mathematical))
                if self.raw:
                    word = list(self.raw['state_data'])
                    end = len(word)-k*c.width
                    word[end-c.width:end] = bits(result, c.width)
                    self.raw['state_data'] = ''.join(word)
                    if command in (Command.CLEAR, Command.LOAD):
                        word = list(self.raw['state_signed'])
                        word[-k-1] = str(signed)
                        self.raw['state_signed'] = ''.join(word)
            self.response.update({name:bits(value, c.widths[name]) for name, value in packed.items()})
        assert self.accepted == self.legal+self.illegal, 'Command accounting assertion failed'
        return event | dict(operation='illegal' if event['causes'] else 'legal')
