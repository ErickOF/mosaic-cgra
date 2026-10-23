"""Independent predicate-bank oracle using lane lists and pre-edge snapshots.

No DUT internals or shared RTL encodings enter prediction. Invalid data is tracked
as an optional logic bit; validity is independent, and every command is planned
fully before the model mutates even one destination lane.
"""

from predicate_unit.transaction import OUTPUTS


def number(value):
    return int(value, 2) if set(value) <= {"0", "1"} else None


def blank():
    return dict.fromkeys(OUTPUTS, 0)


class PredicateModel:
    def __init__(self, config):
        self.c = config
        self.data = [[None] * config.lanes for _ in range(config.depth)]
        self.valid = [[False] * config.lanes for _ in range(config.depth)]
        self.visible = blank()
        self.initialized = False
        self.accepted = 0
        self.stalls = 0

    def reset(self):
        # Payload data is physically unreset. Reset only discards its validity.
        self.valid = [[False] * self.c.lanes for _ in range(self.c.depth)]
        self.visible = blank()
        self.initialized = True

    def evaluate(self, p):
        c = self.c
        out = blank()
        event = {"kind": "bubble", "updates": [], "cause": "none"}
        if p["i_valid"] != "1":
            return out, event
        out["o_valid"] = 1
        op, mask, write = (
            number(p[name]) for name in ("i_opcode", "i_lane_mask", "i_write_enable")
        )
        addresses = [
            number(p[name])
            for name in ("i_source_a_addr", "i_source_b_addr", "i_destination_addr")
        ]
        event.update(opcode=op, mask=mask, write=write, addresses=addresses)
        cause = "none"
        active = [k for k in range(c.lanes) if mask is not None and mask & (1 << k)]
        needs = [op is not None and 3 <= op <= 7, op is not None and 5 <= op <= 7]
        if op is None or mask is None or write is None:
            cause = "controls"
        elif op > 8:
            cause = "opcode"
        elif op == 8 and not write:
            cause = "invalidate_write"
        elif active:
            for port, needed in enumerate(needs):
                if needed:
                    address = addresses[port]
                    if address is None or address >= c.depth:
                        cause = "source_a_address" if port == 0 else "source_b_address"
                        break
                    if any(not self.valid[address][k] for k in active):
                        cause = "source_a_valid" if port == 0 else "source_b_valid"
                        break
            if (
                cause == "none"
                and write
                and (addresses[2] is None or addresses[2] >= c.depth)
            ):
                cause = "destination_address"
        event["source_validity"] = []
        for port, needed in enumerate(needs):
            address = addresses[port]
            if active and needed and address is not None and address < c.depth:
                event["source_validity"].append(
                    (port, all(self.valid[address][k] for k in active))
                )
        event["cause"] = cause
        if cause != "none":
            out["o_illegal_operation"] = 1
            event["kind"] = "illegal"
            return out, event
        event["kind"] = "invalidate" if op == 8 else "result"
        event["selected"] = active
        if op == 8:
            out["o_invalidated"] = 1
        else:
            result = 0
            for k in active:
                a = self.data[addresses[0]][k] if needs[0] else 0
                b = self.data[addresses[1]][k] if needs[1] else 0
                external = int(p["i_predicate_input"][-1 - k]) if op == 2 else 0
                match op:
                    case 0:
                        value = 0
                    case 1:
                        value = 1
                    case 2:
                        value = external
                    case 3:
                        value = a
                    case 4:
                        value = 1 - a
                    case 5:
                        value = a & b
                    case 6:
                        value = a | b
                    case 7:
                        value = a ^ b
                    case _:
                        raise AssertionError("Unexpected result command")
                result |= value << k
            out.update(
                o_result=result,
                o_result_valid=mask,
                o_any=int(bool(result)),
                o_all=int(bool(mask) and result == mask),
            )
        if write:
            out["o_updated_mask"] = mask
            for k in active:
                dest = addresses[2]
                value = (out["o_result"] >> k) & 1
                event["updates"].append((dest, k, op != 8, value))
        return out, event

    def step(self, p, edge):
        population = sum(sum(row) for row in self.valid)
        if p["i_rstb"] == "0" and (edge or self.c.asynchronous):
            self.reset()
            return {"kind": "reset", "population": population, "updates": []}
        if not edge:
            return {"kind": "clockless", "updates": []}
        if p["i_clock_enable"] == "0":
            self.stalls += 1
            return {"kind": "stall", "updates": []}
        out, event = self.evaluate(p)
        event["before_valid"] = [row.copy() for row in self.valid]
        for dest, k, valid, value in event["updates"]:
            self.valid[dest][k] = valid
            if valid:
                self.data[dest][k] = value
        self.visible = out
        self.accepted += out["o_valid"]
        return event
