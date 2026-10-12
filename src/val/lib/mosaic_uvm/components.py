"""Agent/environment wiring and coverage reporting shared by all suites."""

import json

import cocotb
from pyuvm import ConfigDB, uvm_agent, uvm_component, uvm_env, uvm_sequencer


class ActiveAgent(uvm_agent):
    """Group a suite's sequencer, driver and driver-coordinated passive monitor.

    These monitors observe real DUT signals, but their sample coordination needs
    a driver. Autonomous UVM_PASSIVE sampling is a separate interface policy.
    """

    def build_phase(self):
        super().build_phase()
        assert self.active(), "This suite requires an active agent for sample coordination"
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = self.driver_type("driver", self)
        self.monitor = self.monitor_type("monitor", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)


class CoverageCollector(uvm_component):
    """Own coverage bins/goals; scoreboards submit only checked samples/metrics."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")

    def check_phase(self):
        report = self.report()
        report["simulator"] = cocotb.SIM_NAME
        self.config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        assert report["goals"], "Coverage report has no mandatory goals"
        missing = [name for name, hit in report["goals"].items() if not hit]
        assert not missing, f"Missing functional coverage: {missing}"
        self.logger.info("Coverage PASS: %d goals", len(report["goals"]))


class VerificationEnv(uvm_env):
    """Build an agent, independent checker and separate coverage collector."""

    def build_phase(self):
        self.coverage = self.coverage_type("coverage", self)
        self.agent = self.agent_type("agent", self)
        self.scoreboard = self.scoreboard_type("scoreboard", self)
        ConfigDB().set(self, "scoreboard", "coverage", self.coverage)

    def connect_phase(self):
        self.agent.monitor.ap.connect(self.scoreboard.analysis_export)

    @property
    def sequencer(self):
        """Preserve existing sequence startup paths without duplicating components."""
        return self.agent.sequencer
