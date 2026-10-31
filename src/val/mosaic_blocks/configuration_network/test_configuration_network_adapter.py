"""PyUVM conformance test for the released tile-shell protocol translation."""

from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from configuration_network.adapter_contract import DEFAULTS, ALIASES, PORTS
from configuration_network.adapter_scoreboard import AdapterScoreboard
from configuration_network.adapter_sequences import AdapterSequence
from configuration_network.agent import NetworkAgent
from configuration_network.coverage import NetworkCoverage
from mosaic_uvm.components import VerificationEnv


@dataclass(frozen=True)
class AdapterConfig:
    parameters: dict
    seed: int
    coverage_file: Path
    random_cycles: int = 0

    @cached_property
    def widths(self):
        a = {alias: self.parameters[n] for n, alias in ALIASES.items()}
        a.update(
            BY=a["D"] // 8,
            SC=max(1, (a["CTX"] - 1).bit_length()),
            SW=max(1, (a["WORDS"] - 1).bit_length()),
        )
        return {n: eval(w, {"__builtins__": {}}, a) for n, (_, w) in PORTS.items()}


class AdapterEnv(VerificationEnv):
    agent_type = NetworkAgent
    scoreboard_type = AdapterScoreboard
    coverage_type = NetworkCoverage


@test(timeout_time=1, timeout_unit="ms")
class ConfigurationAdapterTest(uvm_test):
    def build_phase(self):
        p = {
            n: int(os.getenv("CONFIGURATION_ADAPTER_" + n, str(v)), 0)
            for n, v in DEFAULTS.items()
        }
        self.c = AdapterConfig(
            p,
            int(os.getenv("CONFIGURATION_ADAPTER_SEED", "20261026")),
            Path(os.environ["CONFIGURATION_ADAPTER_COVERAGE_FILE"]),
        )
        for n, w in self.c.widths.items():
            assert len(getattr(cocotb.top, n)) == w, n
        for n, v in p.items():
            assert int(getattr(cocotb.top, n).value) == v, n
        self.active = dict(pre=Event(), post=Event(), records=[])
        ConfigDB().set(self, "env.*", "config", self.c)
        ConfigDB().set(self, "env.*", "active", self.active)
        self.env = AdapterEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        await AdapterSequence(self.c, self.active, self.env.coverage).start(
            self.env.sequencer
        )
        self.drop_objection()
