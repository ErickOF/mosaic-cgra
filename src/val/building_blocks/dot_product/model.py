"""Independent arbitrary-precision products, mathematical ranges and edge history."""
from mosaic_uvm.logic import bits
from dot_product.transaction import CONTROLS, OUTPUTS


def known(value):
    return set(value) <= {'0', '1'}


def element(word, index, width):
    end = len(word) - index * width
    return word[end - width:end]


def interpret(value, width, signed):
    return value - (1 << width) if signed and value >= 1 << (width - 1) else value


def empty(config):
    return {name: '0' * config.widths[name] for name in OUTPUTS}


def causes(config, ports):
    errors = {name for name in CONTROLS if not known(ports[name])}
    if ports['i_accumulate'] == '1' and not config.accumulate:
        errors.add('unsupported_accumulate')
    if ports['i_saturate'] == '1' and not config.saturation:
        errors.add('unsupported_saturation')
    return errors


def predict(config, ports):
    """Do not reuse RTL widths, tree nodes, carry bits or sign-overflow equations."""
    response = empty(config)
    assert known(ports['i_valid']), 'Protocol assertion failed: i_valid'
    if ports['i_valid'] == '0':
        return response, dict(kind='bubble')
    response['o_valid'] = '1'
    errors = causes(config, ports)
    if errors:
        response['o_illegal_operation'] = '1'
        return response, dict(kind='illegal', causes=errors)
    signed = ports['i_signed'] == '1'
    accumulate = ports['i_accumulate'] == '1'
    saturate = ports['i_saturate'] == '1'
    mask = int(ports['i_term_mask'], 2)
    products = []
    for index in range(config.terms):
        if mask & (1 << index):
            a = element(ports['i_operand_a'], index, config.element)
            b = element(ports['i_operand_b'], index, config.element)
            assert known(a), 'Protocol assertion failed: i_operand_a'
            assert known(b), 'Protocol assertion failed: i_operand_b'
            products.append(interpret(int(a, 2), config.element, signed) *
                            interpret(int(b, 2), config.element, signed))
        else:
            products.append(0)
    dot = sum(products)
    if accumulate:
        assert known(ports['i_accumulator']), 'Protocol assertion failed: i_accumulator'
        accumulator = interpret(int(ports['i_accumulator'], 2), config.width, signed)
    else:
        accumulator = 0
    total = dot + accumulator
    modulus = 1 << config.width
    low, high = (-(modulus // 2), modulus // 2 - 1) if signed else (0, modulus - 1)
    wrapped = total % modulus
    final = min(high, max(low, total)) % modulus if saturate else wrapped
    flags = dict(o_result=final, o_active_count=mask.bit_count(),
                 o_carry=int(accumulate and not signed and total > high),
                 o_overflow=int(accumulate and signed and not low <= total <= high),
                 o_saturated=int(saturate and final != wrapped), o_zero=int(final == 0),
                 o_negative=int(signed and final >= modulus // 2))
    response.update({name: bits(value, config.widths[name]) for name, value in flags.items()})
    return response, dict(kind='legal', modes=(int(signed), int(accumulate), int(saturate)),
                         mask=mask, products=products, dot=dot, total=total, low=low,
                         high=high, final=final, response=response)


class DotProductModel:
    def __init__(self, config):
        self.c = config
        self.history = [empty(config) for _ in range(config.latency)]
        self.events = [None] * config.latency
        self.initialized = config.latency == 0
        self.accepted = self.emitted = self.discarded = 0

    @property
    def occupancy(self):
        return sum(word['o_valid'] == '1' for word in self.history)

    def reset(self):
        # The response currently visible was counted when it first appeared.
        self.discarded += sum(word['o_valid'] == '1' for word in self.history[:-1])
        self.history = [empty(self.c) for _ in range(self.c.latency)]
        self.events = [None] * self.c.latency
        self.initialized = True

    def output(self, ports):
        return predict(self.c, ports)[0] if not self.c.latency else self.history[-1]

    def step(self, ports, edge):
        if self.c.latency:
            if not edge:
                return dict(kind='no_edge')
            assert known(ports['i_rstb']), 'Protocol assertion failed: i_rstb'
            if ports['i_rstb'] == '0':
                before = self.occupancy
                self.reset()
                return dict(kind='reset', occupancy=before)
            assert known(ports['i_clock_enable']), 'Protocol assertion failed: i_clock_enable'
            if ports['i_clock_enable'] == '0':
                return dict(kind='stall', occupancy=self.occupancy)
        response, event = predict(self.c, ports)
        self.accepted += response['o_valid'] == '1'
        if self.c.latency:
            self.history = [response, *self.history[:-1]]
            self.events = [event, *self.events[:-1]]
        self.emitted += self.output(ports)['o_valid'] == '1'
        pending = sum(word['o_valid'] == '1' for word in self.history[:-1])
        assert self.accepted == self.emitted + self.discarded + pending, 'Response conservation'
        return event
