"""Native endpoint environment: storage and safe activation stay outside the fabric."""

from collections import deque
import random
from configuration_network.layout import endpoint, dimensions, crc32c
from configuration_network.transaction import field

REQUEST_WIDTHS = dict(
    command="C",
    transaction_id="TI",
    sequence_id="32",
    tag="TG",
    owner_id="OW",
    kernel_id="K",
    package_id="P",
    epoch="EP",
    context_id="CI",
    expected_version="V",
    word_index="WI",
    write_data="D",
    write_strobe="BY",
    expected_crc="32",
)
RESPONSE_WIDTHS = dict(
    transaction_id="TI",
    sequence_id="32",
    epoch="EP",
    status="4",
    error_code="8",
    read_data="D",
    context_version="V",
    image_crc="32",
    prepared="1",
)
COMMIT_WIDTHS = dict(
    context_id="CI",
    context_version="V",
    package_id="P",
    owner_id="OW",
    kernel_id="K",
    epoch="EP",
    image_crc="32",
)


def native_request(p, e, a):
    return {
        n: field(p, "o_endpoint_request_" + n, e, eval(w, {}, a))
        for n, w in REQUEST_WIDTHS.items()
    }


class NativeEndpoint:
    def __init__(self, p, index):
        self.p = p
        self.a = dimensions(p)
        self.index = index
        self.descriptor = endpoint(p, index)
        self.contexts = {}
        self.prepared = None
        self.active = None

    def context(self, index):
        if index not in self.contexts:
            self.contexts[index] = dict(
                words=[0] * self.descriptor["words"],
                written=0,
                version=0,
                validated=False,
                loading=False,
                owner=0,
                kernel=0,
                package=0,
            )
        return self.contexts[index]

    def crc(self, index):
        c = self.context(index)
        return crc32c(b"".join(w.to_bytes(self.a["BY"], "little") for w in c["words"]))

    def execute(self, r, quiescent=True, forced_error=0):
        a = self.a
        cmd = r["command"]
        ci = r["context_id"]
        c = self.context(ci)
        result = {n: r.get(n, 0) for n in ("transaction_id", "sequence_id", "epoch")}
        result.update(
            status=0,
            error_code=0,
            read_data=0,
            context_version=c["version"],
            image_crc=self.crc(ci),
            prepared=int(self.prepared is not None),
        )

        def reject(code):
            result.update(status=1, error_code=code)
            return result

        if forced_error:
            return reject(forced_error)
        if cmd in (1, 4, 6) and self.active and ci == self.active["context_id"]:
            return reject(14)
        if cmd in (1, 3, 6) and r["expected_version"] != c["version"]:
            return reject(9)
        identity = (r["owner_id"], r["kernel_id"], r["package_id"])
        if cmd in (3, 6) and identity != (c["owner"], c["kernel"], c["package"]):
            return reject(24)
        if cmd == 1:
            if not c["loading"]:
                c["version"] = (c["version"] + 1) % (1 << a["V"])
                c["written"] = 0
                c["loading"] = True
                c["owner"], c["kernel"], c["package"] = identity
            elif identity != (c["owner"], c["kernel"], c["package"]):
                return reject(24)
            c["validated"] = False
            self.prepared = None
            index = r["word_index"]
            word = c["words"][index]
            for b in range(a["BY"]):
                if r["write_strobe"] >> b & 1:
                    word = (word & ~(255 << (8 * b))) | (
                        r["write_data"] >> (8 * b) & 255
                    ) << (8 * b)
                    c["written"] |= 1 << (index * a["BY"] + b)
            c["words"][index] = word
        elif cmd == 2:
            result["read_data"] = c["words"][r["word_index"]]
        elif cmd == 3:
            if c["written"] != (1 << (self.descriptor["words"] * a["BY"])) - 1:
                return reject(14)
            if r["expected_crc"] != self.crc(ci):
                return reject(23)
            c["validated"] = True
            c["loading"] = False
        elif cmd == 4:
            c["validated"] = False
            c["loading"] = False
            c["written"] = 0
            if self.prepared and self.prepared["context_id"] == ci:
                self.prepared = None
        elif cmd == 5:
            result["read_data"] = (
                int(c["validated"])
                | int(c["loading"]) << 1
                | int(self.active is not None and self.active["context_id"] == ci) << 2
            )
        elif cmd == 6:
            if not c["validated"] or not quiescent or r["expected_crc"] != self.crc(ci):
                return reject(17)
            self.prepared = dict(
                context_id=ci,
                context_version=c["version"],
                owner_id=c["owner"],
                kernel_id=c["kernel"],
                package_id=c["package"],
                image_crc=self.crc(ci),
            )
        elif cmd == 7:
            self.prepared = None
        else:
            return reject(2)
        result.update(
            context_version=c["version"],
            image_crc=self.crc(ci),
            prepared=int(self.prepared is not None),
        )
        return result

    def cancel(self):
        self.prepared = None
        for index, c in self.contexts.items():
            if self.active is None or self.active["context_id"] != index:
                c.update(validated=False, loading=False, written=0)


class EndpointServer:
    def __init__(self, p, seed):
        self.p = p
        self.a = dimensions(p)
        self.rng = random.Random(seed)
        self.safe = (1 << self.a["NE"]) - 1
        self.quiescent = self.safe
        self.stalls = False
        self.delays = {}
        self.drop = set()
        self.errors = {}
        self.commit_errors = set()
        self.commit_drop = set()
        self.cancel_block = 0
        self.reset()

    def reset(self):
        self.endpoints = [NativeEndpoint(self.p, e) for e in range(self.a["NE"])]
        self.responses = [deque() for _ in self.endpoints]
        self.acks = [None for _ in self.endpoints]
        self.time = 0
        self.native_history = []
        self.commit_history = []

    def drive(self):
        a = self.a
        v = {}

        def put(n, e, width, x):
            v[n] = v.get(n, 0) | (x << (e * width))

        v.update(
            i_endpoint_power_safe=self.safe,
            i_endpoint_quiescent=self.quiescent,
            i_endpoint_cancel_ack=((1 << a["NE"]) - 1) & ~self.cancel_block,
            i_endpoint_request_ready=0,
            i_endpoint_response_valid=0,
            i_endpoint_commit_ready=0,
            i_endpoint_commit_ack_valid=0,
            i_endpoint_prepared_retained=0,
            i_endpoint_commit_error=0,
        )
        for e, native in enumerate(self.endpoints):
            if native.prepared is not None:
                v["i_endpoint_prepared_retained"] |= 1 << e
            if not self.stalls or self.rng.randrange(4):
                v["i_endpoint_request_ready"] |= 1 << e
            if (
                native.prepared is not None
                and self.safe >> e & 1
                and self.quiescent >> e & 1
            ):
                v["i_endpoint_commit_ready"] |= 1 << e
            if self.responses[e] and self.responses[e][0][0] <= self.time:
                r = self.responses[e][0][1]
                v["i_endpoint_response_valid"] |= 1 << e
                for n, w in RESPONSE_WIDTHS.items():
                    put("i_endpoint_response_" + n, e, eval(w, {}, a), r[n])
            if self.acks[e] and self.acks[e][0] <= self.time:
                v["i_endpoint_commit_ack_valid"] |= 1 << e
                active = self.acks[e][1]
                v["i_endpoint_commit_error"] |= int(e in self.commit_errors) << e
                for n, w in COMMIT_WIDTHS.items():
                    put("i_endpoint_active_" + n, e, eval(w, {}, a), active[n])
        return v

    def step(self, p):
        if not p["i_reset_n"]:
            self.reset()
            return
        a = self.a
        for e, native in enumerate(self.endpoints):
            if p["o_endpoint_cancel"] >> e & 1 and p["i_endpoint_cancel_ack"] >> e & 1:
                self.responses[e].clear()
                self.acks[e] = None
                native.cancel()
                continue
            if (
                p["i_endpoint_response_valid"] >> e & 1
                and p["o_endpoint_response_ready"] >> e & 1
            ):
                if self.responses[e]:
                    self.responses[e].popleft()
            if (
                p["i_endpoint_commit_ack_valid"] >> e & 1
                and p["o_endpoint_commit_ack_ready"] >> e & 1
            ):
                self.acks[e] = None
            if (
                p["o_endpoint_request_valid"] >> e & 1
                and p["i_endpoint_request_ready"] >> e & 1
            ):
                r = native_request(p, e, a)
                self.native_history.append((self.time, e, r))
                result = native.execute(
                    r, bool(self.quiescent >> e & 1), self.errors.get(e, 0)
                )
                if e not in self.drop:
                    delay = self.delays.get(e, 1 + self.rng.randrange(8))
                    self.responses[e].append((self.time + delay, result))
            if p["o_endpoint_commit_valid"] >> e & 1:
                active = {
                    n: field(p, "o_endpoint_commit_" + n, e, eval(w, {}, a))
                    for n, w in COMMIT_WIDTHS.items()
                }
                assert native.prepared is not None, ("Unprepared native commit", e)
                assert all(active[n] == native.prepared[n] for n in native.prepared)
                native.active = active.copy()
                native.prepared = None
                self.commit_history.append((self.time, e, active))
                if e not in self.commit_drop:
                    self.acks[e] = (self.time + 1 + e % 5, active)
        self.time += 1
