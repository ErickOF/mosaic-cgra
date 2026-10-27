"""Ingress-to-native exact-once ledger and independent ordered response retirement."""

from collections import deque
from pyuvm import ConfigDB, uvm_subscriber
from configuration_network.layout import endpoint, preflight, RSP, pack_fields, crc32c
from configuration_network.transaction import OUTPUTS, field
from configuration_network.model import native_request, NativeEndpoint, RESPONSE_WIDTHS


class NetworkScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.reset()

    def reset(self):
        self.order = deque()
        self.by_sequence = {}
        self.native = [deque() for _ in range(self.c.aliases["NE"])]
        self.pending = {}
        self.sequence = 0
        self.held = {}
        self.references = [
            NativeEndpoint(self.c.parameters, e) for e in range(self.c.aliases["NE"])
        ]

    def write(self, obs):
        if obs.phase != "pre":
            return
        p, a = obs.ports, self.c.aliases
        self.coverage.cycles += 1
        if p["i_reset_n"]:
            for name in OUTPUTS:
                assert p[name] is not None, (
                    "Unknown output",
                    name,
                    obs.item.get_name(),
                )
        if not p["i_reset_n"]:
            self.reset()
            assert not p["o_cfg_request_ready"] and not p["o_endpoint_request_valid"]
            assert p["o_execution_hold"]
            return
        if p["i_flush"]:
            self.order.clear()
            self.by_sequence.clear()
            self.native = [deque() for _ in self.native]
            self.pending.clear()
            self.held.clear()
            assert not p["o_cfg_request_ready"] and not p["o_endpoint_request_valid"]
            return
        if self.active.get("diagnostic"):
            self.held.clear()
            return
        # Hold complete output records under master backpressure.
        for m in range(a["NM"]):
            if p["o_cfg_response_valid"] >> m & 1:
                current = tuple(
                    field(p, n, m, self.c.widths[n] // a["NM"])
                    for n in OUTPUTS
                    if n.startswith("o_cfg_response_") and n != "o_cfg_response_valid"
                )
                if m in self.held:
                    assert self.held[m] == current, "Unstable stalled root record"
                if not p["i_cfg_response_ready"] >> m & 1:
                    self.held[m] = current
                else:
                    self.held.pop(m, None)
            else:
                assert m not in self.held, "Stalled response disappeared"
        for m in range(a["NM"]):
            if p["i_cfg_request_valid"] >> m & 1 and p["o_cfg_request_ready"] >> m & 1:
                r = {
                    n.removeprefix("i_cfg_request_"): field(
                        p, n, m, self.c.widths[n] // a["NM"]
                    )
                    for n in self.c.widths
                    if n.startswith("i_cfg_request_") and n != "i_cfg_request_valid"
                }
                r.update(
                    master=m,
                    sequence_id=self.sequence,
                    transaction_id=self.sequence % (1 << a["TI"]),
                )
                self.sequence += 1
                code = preflight(
                    self.c.parameters,
                    r,
                    p["o_configuration_epoch"],
                    p["i_endpoint_power_safe"],
                )
                endpoints = [
                    e for e in range(a["NE"]) if r["destination_mask"] >> e & 1
                ]
                synthetic = not endpoints
                if synthetic:
                    endpoints = [0]
                obj = dict(
                    request=r,
                    remaining=sorted(
                        endpoints, key=lambda e: endpoint(self.c.parameters, e)["id"]
                    ),
                    results={},
                    failure=0,
                    success=0,
                    timeout=0,
                    absent=0,
                    first=True,
                    synthetic=synthetic,
                )
                for e in endpoints:
                    d = endpoint(self.c.parameters, e)
                    if code or not d["present"] and not synthetic:
                        ec = 3 if not d["present"] and not synthetic else code
                        status = 4 if not d["present"] and not synthetic else 1
                        obj["results"][e] = dict(
                            status=status,
                            error_code=ec,
                            read_data=0,
                            context_version=0,
                            image_crc=0,
                            prepared=0,
                        )
                        obj["failure"] |= 1 << e
                        if status == 4:
                            obj["absent"] |= 1 << e
                    elif synthetic:
                        obj["results"][e] = dict(
                            status=0,
                            error_code=0,
                            read_data=0,
                            context_version=0,
                            image_crc=0,
                            prepared=0,
                        )
                        obj["success"] |= 1 << e
                    else:
                        self.native[e].append(obj)
                self.order.append(obj)
                self.by_sequence[r["sequence_id"]] = obj
                self.coverage.accepted += 1
                self.coverage.hit(f"command_{r['command']}")
        for e in range(a["NE"]):
            if (
                p["o_endpoint_request_valid"] >> e & 1
                and p["i_endpoint_request_ready"] >> e & 1
            ):
                assert self.native[e], ("Unselected/duplicate endpoint mutation", e)
                obj = self.native[e].popleft()
                r = obj["request"]
                actual = native_request(p, e, a)
                for n, expected in r.items():
                    native_name = {
                        "destination_mask": None,
                        "flags": None,
                        "protocol": None,
                        "master": None,
                    }.get(n, n)
                    if native_name is not None:
                        assert actual[native_name] == expected, (
                            e,
                            n,
                            actual[native_name],
                            expected,
                        )
                result = self.references[e].execute(
                    actual,
                    bool(p["i_endpoint_quiescent"] >> e & 1),
                    self.active.get("endpoint_errors", {}).get(e, 0),
                )
                self.pending[e] = obj, result
                self.coverage.delivered += 1
                self.coverage.hit(f"endpoint_{e}")
            if (
                p["i_endpoint_response_valid"] >> e & 1
                and p["o_endpoint_response_ready"] >> e & 1
            ):
                assert e in self.pending, ("Unexpected native result", e)
                obj, result = self.pending.pop(e)
                for n, w in RESPONSE_WIDTHS.items():
                    actual = field(p, "i_endpoint_response_" + n, e, eval(w, {}, a))
                    assert actual == result[n], (
                        "Native result model",
                        e,
                        n,
                        actual,
                        result[n],
                    )
                obj["results"][e] = result
                obj["success" if result["status"] == 0 else "failure"] |= 1 << e
        for m in range(a["NM"]):
            if (
                p["o_cfg_response_valid"] >> m & 1
                and p["i_cfg_response_ready"] >> m & 1
            ):
                assert self.order, "Unowned root completion"
                obj = self.order[0]
                r = obj["request"]
                e = obj["remaining"].pop(0)
                assert r["master"] == m and e in obj["results"], (
                    "Early/reordered root response",
                    e,
                    r,
                )
                result = obj["results"][e]
                last = not obj["remaining"]
                checks = dict(
                    transaction_success=int(
                        last and not obj["failure"] and result["status"] == 0
                    ),
                    endpoint_type=0
                    if obj["synthetic"]
                    else endpoint(self.c.parameters, e)["type"],
                    command=r["command"],
                    transaction_id=r["transaction_id"],
                    sequence_id=r["sequence_id"],
                    protocol=1,
                    endpoint_id=((1 << a["EI"]) - 1)
                    if obj["synthetic"]
                    else endpoint(self.c.parameters, e)["id"],
                    context_id=r["context_id"],
                    tag=r["tag"],
                    epoch=r["epoch"],
                    first=int(obj["first"]),
                    last=int(last),
                    status=result["status"],
                    error_code=result["error_code"],
                    read_data=result["read_data"],
                    context_version=result["context_version"],
                    crc=result["image_crc"],
                    prepared=result["prepared"],
                )
                for n, v in checks.items():
                    name = "o_cfg_response_" + n
                    actual = field(p, name, m, self.c.widths[name] // a["NM"])
                    assert actual == v, (
                        "Root record",
                        n,
                        actual,
                        v,
                        e,
                        obs.item.get_name(),
                    )
                for n, k in [
                    ("failure_mask", "failure"),
                    ("success_mask", "success"),
                    ("timeout_mask", "timeout"),
                    ("not_present_mask", "absent"),
                ]:
                    expected = obj[k] if last and not obj["synthetic"] else 0
                    assert field(p, "o_cfg_response_" + n, m, a["NE"]) == expected, (
                        n,
                        expected,
                    )
                record = {
                    n.removeprefix("o_cfg_response_"): field(
                        p, n, m, self.c.widths[n] // a["NM"]
                    )
                    for n in OUTPUTS
                    if n.startswith("o_cfg_response_") and n != "o_cfg_response_valid"
                }
                rename = {
                    "transaction": "transaction_id",
                    "endpoint": "endpoint_id",
                    "version": "context_version",
                    "image_crc": "crc",
                }
                fields = [(record[rename.get(n, n)], eval(w, {}, a)) for n, w in RSP]
                fields += [
                    (record["endpoint_type"], a["ET"]),
                    (record["first"], 1),
                    (record["last"], 1),
                    (record["transaction_success"], 1),
                ]
                fields += [
                    (record[n], a["NE"])
                    for n in (
                        "failure_mask",
                        "success_mask",
                        "timeout_mask",
                        "not_present_mask",
                    )
                ]
                bits = pack_fields(fields)
                size = (sum(w for _, w in fields) + 7) // 8
                assert record["packet_crc"] == (
                    crc32c(bits.to_bytes(size, "little"))
                    if self.c.parameters["ENABLE_PACKET_CRC"]
                    else 0
                )
                self.active["records"].append(record)
                self.coverage.completed += 1
                obj["first"] = False
                if last:
                    self.order.popleft()
                    self.by_sequence.pop(r["sequence_id"], None)
        for e in range(a["NE"]):
            if p["o_endpoint_commit_valid"] >> e & 1:
                from configuration_network.model import COMMIT_WIDTHS

                actual = {
                    n: field(p, "o_endpoint_commit_" + n, e, eval(w, {}, a))
                    for n, w in COMMIT_WIDTHS.items()
                }
                assert self.references[e].prepared is not None, (
                    "Commit before preparation",
                    e,
                )
                assert all(
                    actual[n] == v for n, v in self.references[e].prepared.items()
                )
                self.references[e].active = actual
                self.references[e].prepared = None
                assert p["o_execution_hold"], (
                    "Execution was released during native activation"
                )
        assert not p["o_error"], (
            "Unexpected transport error",
            p["o_error_code"],
            obs.item.get_name(),
        )

    def check_phase(self):
        assert not self.order and not self.pending and not any(self.native), (
            "Outstanding checked traffic"
        )
