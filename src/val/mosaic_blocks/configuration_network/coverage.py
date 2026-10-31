"""Checked scenario goals and endpoint-copy accounting."""

import os
from collections import Counter
from configuration_network.layout import published_parameters
from mosaic_uvm.components import CoverageCollector


class NetworkCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cycles = 0
        self.accepted = 0
        self.delivered = 0
        self.completed = 0
        self.bins = Counter()
        self.goals = {}

    def hit(self, name):
        self.bins[name] += 1

    def report(self):
        return dict(
            status="PASS" if self.goals and all(self.goals.values()) else "FAIL",
            framework="PyUVM",
            scenario="flush-overlap"
            if os.getenv("CONFIGURATION_NETWORK_FOCUSED_FLUSH") == "1"
            else "full",
            validation_mode="Python-only",
            hdl_assertions="NOT_RUN",
            parameters=published_parameters(self.config.parameters),
            seed=self.config.seed,
            random_cycles=self.config.random_cycles,
            cycles=self.cycles,
            accepted=self.accepted,
            delivered=self.delivered,
            completed=self.completed,
            bins=dict(self.bins),
            goals=self.goals,
            synthesis="Design Compiler (deferred)",
        )
