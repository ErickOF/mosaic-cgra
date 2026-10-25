"""Independent unbounded integers and an enabled-edge transaction deadline ledger."""
from mosaic_uvm.logic import bits
from multiplier.transaction import CONTROLS, OUTPUTS


def known(value):
    return set(value) <= {'0', '1'}


def interpret(word, signed):
    value = int(word, 2)
    return value - (1 << len(word)) if signed and word[0] == '1' else value


def empty(config):
    return {name: '0' * config.widths[name] for name in OUTPUTS}


def predict(config, ports):
    """Interpret each raw operand mathematically; do not reuse RTL extension casts."""
    response = empty(config)
    assert known(ports['i_valid']), 'Protocol assertion failed: i_valid'
    if ports['i_valid'] == '0':
        return response, dict(kind='bubble')
    for name in (*CONTROLS, 'i_operand_a', 'i_operand_b'):
        assert known(ports[name]), f'Protocol assertion failed: {name}'
    signed_a, signed_b = (ports[name] == '1' for name in CONTROLS)
    a = interpret(ports['i_operand_a'], signed_a)
    b = interpret(ports['i_operand_b'], signed_b)
    product = a * b
    signed = signed_a or signed_b
    encoded = product % (1 << config.product_width)
    response.update(o_valid='1', o_product=bits(encoded, config.product_width),
                    o_product_signed=bits(int(signed), 1), o_zero=bits(int(product == 0), 1),
                    o_negative=bits(int(product < 0), 1))
    return response, dict(kind='valid', modes=(int(signed_a), int(signed_b)),
                         a=a, b=b, product=product, response=response)


class MultiplierModel:
    """Schedule expected products without copying the RTL register arrays."""
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
