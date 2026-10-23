"""Independent integer arithmetic and an enabled-edge response deadline ledger."""

from mosaic_uvm.logic import bits
from scalar_alu.model import known, signed_value
from scalar_alu.model import predict as predict_alu

from vector_lane.transaction import OUTPUTS


def empty(c):
    return {name: "0" * c.widths[name] for name in OUTPUTS}


def predict(c, p):
    """Decode suppression first; compute mathematical values without RTL intermediates."""
    r = dict.fromkeys(OUTPUTS, 0)

    def finish(kind, **event):
        response = {name: bits(value, c.widths[name]) for name, value in r.items()}
        return response, dict(kind=kind, response=response, **event)

    assert known(p["i_valid"]), "VECTOR_LANE_PROTOCOL: i_valid"
    if p["i_valid"] == "0":
        return finish("bubble")
    r["o_valid"] = 1
    if p["i_lane_enable"] == "0":
        r["o_suppressed"] = 1
        return finish("suppressed", cause="mask")
    if (
        p["i_lane_enable"] == "1"
        and p["i_predicate_enable"] == "1"
        and p["i_execute_predicate"] == "0"
    ):
        r["o_suppressed"] = 1
        return finish("suppressed", cause="predicate")
    op = int(p["i_opcode"], 2) if known(p["i_opcode"]) else None
    cause = None
    if p["i_lane_enable"] != "1":
        cause = "lane_enable"
    elif not known(p["i_predicate_enable"]):
        cause = "predicate_enable"
    elif p["i_predicate_enable"] == "1" and not known(p["i_execute_predicate"]):
        cause = "execute_predicate"
    elif op is None:
        cause = "opcode"
    elif not known(p["i_signed"]):
        cause = "signed"
    elif not known(p["i_saturate"]):
        cause = "saturate"
    elif op > 21:
        cause = "reserved"
    elif op in (18, 19) and not c.minmax:
        cause = "minmax_disabled"
    elif op == 20 and not c.mul:
        cause = "mul_disabled"
    elif op == 21 and not c.mac:
        cause = "mac_disabled"
    elif op == 15 and not known(p["i_select_predicate"]):
        cause = "select_predicate"
    elif p["i_saturate"] == "1" and (not c.saturation or op not in (0, 1, 21)):
        cause = "unsupported_saturation"
    if cause:
        r["o_illegal_operation"] = 1
        return finish("illegal", cause=cause, opcode=op)
    signed, saturate = (p[k] == "1" for k in ("i_signed", "i_saturate"))
    need_a = op != 17 and (op != 15 or p["i_select_predicate"] == "1")
    need_b = op not in (5, 16) and (op != 15 or p["i_select_predicate"] == "0")
    for name, needed in (
        ("i_operand_a", need_a),
        ("i_operand_b", need_b),
        ("i_accumulator", op == 21),
    ):
        assert not needed or known(p[name]), f"VECTOR_LANE_PROTOCOL: {name}"
    a, b = (int(p[k], 2) if known(p[k]) else 0 for k in ("i_operand_a", "i_operand_b"))
    left, right = (signed_value(v, c.element) if signed else v for v in (a, b))
    raw = None
    if op < 20:
        alu, _ = predict_alu(c.alu, p | {"i_enable": "1", "i_predicate": p["i_select_predicate"]})
        for k in ("o_predicate", "o_carry", "o_borrow", "o_overflow", "o_saturated"):
            r[k] = int(alu[k], 2)
        comparison = 9 <= op <= 14
        r["o_predicate_valid"] = int(comparison)
        r["o_result_format"] = 0 if comparison else 1
        r["o_result_signed"] = int(signed and not comparison)
        value = int(alu["o_result"], 2)
        if signed and not comparison:
            value = signed_value(value, c.element)
        r["o_carry"] &= not signed
        r["o_borrow"] &= not signed
    else:
        raw = left * right
        r["o_result_signed"] = int(signed)
        r["o_result_format"] = 2 if op == 20 else 3
        if op == 21:
            accumulator = int(p["i_accumulator"], 2)
            raw += signed_value(accumulator, c.accumulator) if signed else accumulator
            low = -(1 << (c.accumulator - 1)) if signed else 0
            high = (1 << (c.accumulator - 1)) - 1 if signed else (1 << c.accumulator) - 1
            r["o_carry"] = int(not signed and raw > high)
            r["o_overflow"] = int(signed and not low <= raw <= high)
            r["o_saturated"] = int(saturate and not low <= raw <= high)
            value = min(high, max(low, raw)) if saturate else raw
        else:
            value = raw
    value %= 1 << c.accumulator
    r.update(
        o_write_enable=1,
        o_result=value,
        o_zero=int(value == 0),
        o_negative=int(bool(r["o_result_signed"]) and bool(value >> (c.accumulator - 1))),
    )
    return finish(
        "legal",
        opcode=op,
        signed=int(signed),
        saturate=int(saturate),
        a=a,
        b=b,
        raw=raw,
        family="alu" if op < 20 else "mul" if op == 20 else "mac",
    )


class LaneModel:
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
