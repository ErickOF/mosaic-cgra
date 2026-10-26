"""Checked functional goals and reproducible evidence."""

from collections import Counter
from mosaic_uvm.components import CoverageCollector


class MeshCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cycles = self.accepted = self.delivered = self.expected_copies = 0
        self.bins = Counter()
        self.goals = {}

    def hit(self, name):
        self.bins[name] += 1

    def report(self):
        return dict(
            status="PASS" if all(self.goals.values()) else "FAIL",
            goals=self.goals,
            parameters=self.config.parameters,
            seed=self.config.seed,
            cycles=self.cycles,
            accepted=self.accepted,
            delivered=self.delivered,
            expected_copies=self.expected_copies,
            bins=dict(self.bins),
            random_cycles=self.config.random_cycles,
            hdl_assertions="NOT_RUN",
            lint="NOT_RUN",
            synthesis="Design Compiler (deferred)",
        )
