"""Native tile-shell environment; each successful write increments its version.

The fabric's generic endpoint model deliberately uses different loading-version
semantics. This model follows the released tile_shell ports/opcodes instead.
"""

from collections import deque
from configuration_network.layout import crc32c


class ShellModel:
    def __init__(self, p):
        self.p = p
        self.words = [[0] * p["CONFIG_WORD_COUNT"] for _ in range(p["CONTEXT_DEPTH"])]
        self.written = [0] * p["CONTEXT_DEPTH"]
        self.versions = [0] * p["CONTEXT_DEPTH"]
        self.validated = [False] * p["CONTEXT_DEPTH"]
        self.active = None
        self.pending = deque()
        self.history = []
        self.cycle = 0
        self.stall = False
        self.delay = 3

    def crc(self, ci):
        return crc32c(
            b"".join(
                w.to_bytes(self.p["CONFIG_DATA_WIDTH"] // 8, "little")
                for w in self.words[ci]
            )
        )

    def execute(self, request):
        cmd, ci, wi = (request[n] for n in ("command", "context_id", "word_index"))
        error, data = 0, 0
        if cmd == 0:
            assert ci != self.active
            value = self.words[ci][wi]
            for byte in range(self.p["CONFIG_DATA_WIDTH"] // 8):
                if request["write_strobe"] >> byte & 1:
                    mask = 255 << (8 * byte)
                    value = (value & ~mask) | (request["write_data"] & mask)
            self.words[ci][wi] = value
            self.written[ci] |= 1 << wi
            self.versions[ci] = (self.versions[ci] + 1) % (
                1 << self.p["CONTEXT_VERSION_WIDTH"]
            )
            self.validated[ci] = False
        elif cmd == 1:
            data = self.words[ci][wi]
        elif cmd == 2:
            error = (
                7
                if self.written[ci] != (1 << self.p["CONFIG_WORD_COUNT"]) - 1
                else 8
                if self.crc(ci) != request["expected_crc"]
                else 0
            )
            self.validated[ci] = not error
        elif cmd == 3:
            assert self.validated[ci]
            self.active = ci
        elif cmd == 4:
            self.validated[ci] = False
            self.written[ci] = 0
        else:
            assert cmd == 5
            data = self.written[ci] | (
                int(self.validated[ci]) << self.p["CONFIG_WORD_COUNT"]
            )
        return dict(
            command=cmd,
            context_id=ci,
            context_version=self.versions[ci],
            crc=self.crc(ci),
            read_data=data,
            error=int(bool(error)),
            error_code=error,
            tag=request["tag"],
        )

    def drive(self):
        ci = self.active or 0
        ports = dict(
            i_power_safe=1,
            i_quiescent=int(not self.pending),
            i_shell_owner_id=0,
            i_shell_kernel_id=3,
            i_shell_request_ready=int(not self.stall),
            i_shell_active_valid=int(self.active is not None),
            i_shell_context_id=ci,
            i_shell_context_version=self.versions[ci],
            i_shell_validated=sum(int(v) << c for c, v in enumerate(self.validated)),
            i_shell_response_valid=0,
        )
        if self.pending and self.pending[0][0] <= self.cycle:
            ports["i_shell_response_valid"] = 1
            ports.update(
                {"i_shell_response_" + n: v for n, v in self.pending[0][1].items()}
            )
        return ports

    def step(self, ports):
        if ports["i_shell_response_valid"] and ports["o_shell_response_ready"]:
            self.pending.popleft()
        if ports["o_shell_request_valid"] and ports["i_shell_request_ready"]:
            request = {
                n: ports["o_shell_request_" + n]
                for n in (
                    "command",
                    "context_id",
                    "word_index",
                    "write_data",
                    "write_strobe",
                    "expected_crc",
                    "tag",
                )
            }
            self.history.append(request)
            self.pending.append((self.cycle + self.delay, self.execute(request)))
        self.cycle += 1
