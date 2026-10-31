"""Passive correlation, native-payload checks and stalled-response stability."""

from pyuvm import ConfigDB, uvm_subscriber


class AdapterScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.pending = None
        self.stalled = None

    def write(self, obs):
        if obs.phase != "pre":
            return
        p = obs.ports
        self.coverage.cycles += 1
        if not p["i_reset_n"]:
            self.pending = self.stalled = None
            return
        if p["i_cancel"]:
            self.pending = self.stalled = None
            return
        if p["i_request_valid"] and p["o_request_ready"]:
            assert self.pending is None
            self.pending = {
                n.removeprefix("i_request_"): v
                for n, v in p.items()
                if n.startswith("i_request_")
            }
            self.coverage.accepted += 1
        if p["o_shell_request_valid"] and p["i_shell_request_ready"]:
            cmd = p["o_shell_request_command"]
            if cmd == 3:
                assert p["i_commit_valid"] and p["o_commit_ready"]
                assert p["o_shell_request_context_id"] == p["i_commit_context_id"]
            else:
                assert self.pending is not None
                r = self.pending
                assert p["o_shell_request_context_id"] == r["context_id"]
                assert p["o_shell_request_owner_id"] == r["owner_id"]
                assert p["o_shell_request_tile_id"] == self.c.parameters["TILE_ID"]
                if r["command"] == 6:
                    assert cmd == 5, "PREPARE must never activate a tile"
                if cmd == 0:
                    assert r["command"] == 1
                    for n in ("word_index", "write_data", "write_strobe"):
                        assert p["o_shell_request_" + n] == r[n]
            self.coverage.delivered += 1
        if p["o_response_valid"]:
            assert self.pending is not None
            for n in ("transaction_id", "sequence_id", "epoch"):
                assert p["o_response_" + n] == self.pending[n]
            response = {
                n.removeprefix("o_response_"): v
                for n, v in p.items()
                if n.startswith("o_response_")
            }
            if self.stalled is not None:
                assert response == self.stalled
            self.stalled = response if not p["i_response_ready"] else None
            if p["i_response_ready"]:
                self.active["records"].append(response)
                self.pending = None
                self.coverage.completed += 1
        if p["o_commit_ack_valid"] and not p["o_commit_error"]:
            assert p["i_shell_active_valid"]
            assert p["o_active_context_id"] == p["i_shell_context_id"]
            assert p["o_active_context_version"] == p["i_shell_context_version"]
            assert p["o_active_owner_id"] == p["i_shell_owner_id"]
            assert p["o_active_kernel_id"] == p["i_shell_kernel_id"]

    def check_phase(self):
        assert self.pending is None
