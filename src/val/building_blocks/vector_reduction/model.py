"""Independent sequential integer reduction and enabled-edge response deadlines."""

from mosaic_uvm.logic import bits

from vector_reduction.transaction import OUTPUTS


def known(word):
    return set(word) <= {"0", "1"}


def interpret(value, width, signed):
    return value - (1 << width) if signed and value & (1 << (width - 1)) else value


def empty(c):
    return {name: "0" * c.widths[name] for name in OUTPUTS}


def predict(c, p):
    response = empty(c)
    assert known(p["i_valid"]), "VECTOR_REDUCTION_PROTOCOL: i_valid"
    if p["i_valid"] == "0":
        return response, {"kind": "bubble"}
    response["o_valid"] = "1"
    op = int(p["i_opcode"], 2) if known(p["i_opcode"]) else None
    mask = int(p["i_element_mask"], 2) if known(p["i_element_mask"]) else None
    cause = None
    if op is None:
        cause = "opcode"
    elif mask is None:
        cause = "mask"
    elif not known(p["i_signed"]):
        cause = "signed"
    elif op > 4:
        cause = "reserved"
    elif op not in c.enabled_opcodes:
        cause = "feature_disabled"
    elif op in (1, 2) and not mask:
        cause = "empty_extrema"
    if cause:
        response["o_illegal_operation"] = "1"
        return response, {"kind": "illegal", "cause": cause, "opcode": op, "mask": mask}
    signed = p["i_signed"] == "1"
    values = []
    raw_values = []
    for k in range(c.count):
        word = p["i_data"][-(k + 1) * c.element : len(p["i_data"]) - k * c.element]
        if mask & (1 << k):
            assert known(word), f"VECTOR_REDUCTION_PROTOCOL: element {k}"
            raw = int(word, 2)
            values.append(interpret(raw, c.element, signed))
            raw_values.append(raw)
    if op == 0:
        value = sum(values)
    elif op == 1:
        value = min(values)
    elif op == 2:
        value = max(values)
    else:
        raw = c.mask if op == 3 else 0
        for element in raw_values:
            raw = raw & element if op == 3 else raw | element
        value = interpret(raw, c.element, signed)
    encoded = value % (1 << c.accumulator)
    response.update(
        o_result=bits(encoded, c.accumulator),
        o_result_format=bits(3 if op == 0 else 1, 2),
        o_result_signed=bits(int(signed), 1),
        o_active_count=bits(len(values), c.count_width),
        o_zero=bits(int(value == 0), 1),
        o_negative=bits(int(signed and value < 0), 1),
    )
    return response, {
        "kind": "legal",
        "opcode": op,
        "signed": int(signed),
        "mask": mask,
        "population": len(values),
        "values": values,
        "raw_values": raw_values,
        "value": value,
        "response": response,
    }


class ReductionModel:
    """Track deadlines and conservation instead of duplicating the RTL stage arrays."""

    def __init__(self, c):
        self.c = c
        self.tick = 0
        self.pending = []
        self.visible = empty(c)
        self.initialized = c.latency == 0
        self.accepted = self.emitted = self.discarded = 0

    @property
    def occupancy(self):
        return len(self.pending) + int(self.visible["o_valid"] == "1")

    def reset(self):
        self.discarded += len(self.pending)
        self.pending.clear()
        self.visible = empty(self.c)
        self.initialized = True

    def output(self, ports):
        return self.visible if self.c.latency else predict(self.c, ports)[0]

    def step(self, ports, edge):
        if self.c.latency:
            if not edge:
                return {"kind": "no_edge"}
            if ports["i_rstb"] == "0":
                occupancy = self.occupancy
                self.reset()
                return {"kind": "reset", "occupancy": occupancy}
            if ports["i_clock_enable"] == "0":
                return {"kind": "stall", "occupancy": self.occupancy}
        response, event = predict(self.c, ports)
        self.tick += 1
        self.accepted += response["o_valid"] == "1"
        if not self.c.latency:
            self.emitted += response["o_valid"] == "1"
        else:
            if response["o_valid"] == "1":
                self.pending.append((self.tick + self.c.latency - 1, response))
            self.visible = empty(self.c)
            if self.pending and self.pending[0][0] == self.tick:
                _, self.visible = self.pending.pop(0)
                self.emitted += 1
        assert self.accepted == self.emitted + self.discarded + len(self.pending)
        return event
