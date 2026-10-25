"""Independent unbounded-integer oracle and enabled-edge transaction ledger."""
from mosaic_uvm.logic import bits
from mac.transaction import CONTROLS, OUTPUTS


def known(value):
    return set(value) <= {'0', '1'}


def interpret(word, signed):
    value = int(word, 2)
    return value - (1 << len(word)) if signed and word[0] == '1' else value


def empty(config):
    return {name: '0' * config.widths[name] for name in OUTPUTS}


def predict(config, ports):
    """Use range comparisons and modulo, independently of RTL carry/sign equations."""
    response = empty(config)
    assert known(ports['i_valid']), 'Protocol assertion failed: i_valid'
    if ports['i_valid'] == '0':
        return response, dict(kind='bubble')
    response['o_valid'] = '1'
    causes = {name for name in CONTROLS if not known(ports[name])}
    if ports['i_saturate'] == '1' and not config.saturation:
        causes.add('unsupported_saturation')
    if causes:
        response['o_illegal_operation'] = '1'
        return response, dict(kind='illegal', causes=causes)
    for name in ('i_operand_a', 'i_operand_b', 'i_accumulator'):
        assert known(ports[name]), f'Protocol assertion failed: {name}'
    signed, saturate = (ports[name] == '1' for name in CONTROLS)
    a, b, accumulator = (interpret(ports[name], signed) for name in
                          ('i_operand_a', 'i_operand_b', 'i_accumulator'))
    product = a * b
    total = accumulator + product
    modulus = 1 << config.width
    low, high = (-(modulus // 2), modulus // 2 - 1) if signed else (0, modulus - 1)
    wrapped = total % modulus
    final = min(high, max(low, total)) % modulus if saturate else wrapped
    flags = dict(o_result=final, o_carry=int(not signed and total > high),
                 o_overflow=int(signed and not low <= total <= high),
                 o_saturated=int(saturate and not low <= total <= high),
                 o_zero=int(final == 0), o_negative=int(signed and final >= modulus // 2))
    response.update({name: bits(value, config.widths[name]) for name, value in flags.items()})
    return response, dict(kind='legal', modes=(int(signed), int(saturate)), a=a, b=b,
                         accumulator=accumulator, product=product, total=total,
                         low=low, high=high, final=interpret(response['o_result'], signed),
                         response=response)


class MacModel:
    """Schedule results by enabled-edge deadlines rather than mirror RTL stages."""
    def __init__(self, config):
        self.c = config
        self.tick = 0
        self.pending = []
        self.visible = empty(config)
        self.initialized = config.latency == 0
        self.accepted = self.emitted = self.discarded = 0

    @property
    def occupancy(self):
        return len(self.pending) + int(self.visible['o_valid'] == '1')

    def reset(self):
        self.discarded += len(self.pending)
        self.pending.clear()
        self.visible = empty(self.c)
        self.initialized = True

    def output(self, ports):
        return predict(self.c, ports)[0] if not self.c.latency else self.visible

    def step(self, ports, edge):
        if self.c.latency:
            if not edge:
                return dict(kind='no_edge')
            assert known(ports['i_rstb']), 'Protocol assertion failed: i_rstb'
            if ports['i_rstb'] == '0':
                occupancy = self.occupancy
                self.reset()
                return dict(kind='reset', occupancy=occupancy)
            assert known(ports['i_clock_enable']), 'Protocol assertion failed: i_clock_enable'
            if ports['i_clock_enable'] == '0':
                return dict(kind='stall', occupancy=self.occupancy)
        response, event = predict(self.c, ports)
        self.accepted += response['o_valid'] == '1'
        self.tick += 1
        if not self.c.latency:
            self.emitted += response['o_valid'] == '1'
        else:
            if response['o_valid'] == '1':
                self.pending.append((self.tick + self.c.latency - 1, response))
            self.visible = empty(self.c)
            if self.pending and self.pending[0][0] == self.tick:
                _, self.visible = self.pending.pop(0)
                self.emitted += 1
        assert self.accepted == self.emitted + self.discarded + len(self.pending)
        return event
