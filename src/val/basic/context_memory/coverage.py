"""Mandatory lifecycle, slice, address, collision, and read-port coverage."""

from collections import Counter
from itertools import combinations, product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from context_memory.model import address
from context_memory.transaction import unpack


def legal_classes(depth):
    return {flags for flags in product((0, 1), repeat=3) if depth > 1 or not (flags[1] and flags[2])}


class ContextMemoryCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.pre_checks = self.held_checks = self.random_checks = 0
        self.transitions, self.violations = Counter(), Counter()
        self.entries = {kind: set() for kind in ("read", "write", "commit", "invalidate")}
        self.reads, self.enables, self.unknowns, self.invalids = set(), set(), set(), set()
        self.populations, self.slices, self.patterns, self.relations = set(), set(), set(), set()
        self.classes, self.reset_classes, self.ignored, self.read_pairs = set(), set(), set(), set()

    def sample(self, observation, active, rising, old_valid, new_valid):
        config, ports, item = self.config, observation.ports, observation.item
        if observation.stage == "pre":
            self.pre_checks += 1
            return
        if observation.stage == "held":
            self.held_checks += 1
            return
        self.checks += 1
        self.random_checks += item.random
        raw_modes = (0, 1) if config.raw else (0,)
        read_requests = []
        for port, (enable, raw, value) in enumerate(zip(unpack(ports["i_read_enable"], 1), unpack(ports["i_read_raw"], 1), unpack(ports["i_read_address"], config.address_width))):
            self.enables.add((port, enable))
            if enable != "1":
                continue
            target = address(value, config.depth)
            if target is not None:
                self.entries["read"].add(target)
                visible_valid = new_valid[target] if ports["i_rstb"] == "1" else "0"
                if visible_valid in ("0", "1") and int(raw) in raw_modes:
                    self.reads.add((port, target, visible_valid, raw))
                read_requests.append((port, target))
                if rising and ports["i_rstb"] == "1":
                    for kind, operation in active.items():
                        if operation is not None:
                            self.relations.add(("read_" + kind, target == operation))
            elif set(value) <= {"0", "1"}:
                self.invalids.add((port, int(value, 2)))
            else:
                self.unknowns.add((port, value))
        self.read_pairs.update((first, index1, second, index2) for (first, index1), (second, index2) in combinations(read_requests, 2))
        if rising:
            flags = tuple(int(active[kind] is not None) for kind in ("write", "commit", "invalidate"))
            if ports["i_rstb"] == "0":
                self.reset_classes.add(flags)
            else:
                self.classes.add(flags)
                for kind, target in active.items():
                    if target is not None:
                        self.entries[kind].add(target)
                for first, second in combinations(("write", "commit", "invalidate"), 2):
                    if active[first] is not None and active[second] is not None:
                        self.relations.add((first + "_" + second, active[first] == active[second]))
            target = address(ports["i_write_address"], config.depth)
            if ports["i_write_enable"] == "1" and target is not None and ports["i_rstb"] == "1":
                population = ports["i_write_mask"].count("1")
                if old_valid[target] in ("0", "1"):
                    self.populations.add((population, old_valid[target]))
                mask_class = "zero" if population == 0 else "full" if population == config.slices else "partial"
                self.patterns.update((name, mask_class) for name in pattern_classes(ports["i_write_data"]))
                for slice_index, enabled in enumerate(reversed(ports["i_write_mask"])):
                    if enabled == "1":
                        self.slices.add((target, slice_index))
        label = item.get_name()
        if label.startswith("ignored:"):
            self.ignored.add(label.split(":")[1])

    def report(self):
        config = self.config
        raw_modes = "01" if config.raw else "0"
        relations = {(kind, True) for kind in ("read_write", "read_commit", "read_invalidate", "write_commit", "write_invalidate")}
        if config.depth > 1:
            relations |= {(kind, False) for kind in ("read_write", "read_commit", "read_invalidate", "write_commit", "write_invalidate", "commit_invalidate")}
        masks = ("zero", "full", "partial") if config.slices > 1 else ("zero", "full")
        goals = dict(
            every_entry_read_written_committed_invalidated=all(values == set(range(config.depth)) for values in self.entries.values()),
            every_read_port_address_validity_raw_cross=self.reads == set(product(range(config.read_ports), range(config.depth), "01", raw_modes)),
            every_read_port_enabled_disabled=self.enables == set(product(range(config.read_ports), "01")),
            every_unused_read_encoding=self.invalids == set(product(range(config.read_ports), range(config.depth, 1 << config.address_width))),
            every_representative_unknown_read_address=self.unknowns == set(product(range(config.read_ports), config.unknown_addresses)),
            mask_population_by_prior_validity=self.populations == set(product(range(config.slices + 1), "01")),
            every_entry_write_slice=self.slices == set(product(range(config.depth), range(config.slices))),
            legal_simultaneous_operation_classes=self.classes == legal_classes(config.depth),
            reset_during_every_legal_operation_class=self.reset_classes == legal_classes(config.depth),
            address_equality_inequality_cross=relations <= self.relations,
            every_read_port_address_pair=self.read_pairs == {(first, address1, second, address2) for first, second in combinations(range(config.read_ports), 2) for address1, address2 in product(range(config.depth), repeat=2)},
            data_patterns_by_mask_class=set(product(("zero", "one", "walking_one", "walking_zero", "alternating"), masks)) <= self.patterns,
            ignored_controls_addresses_and_unmasked_data={"disabled_reads", "zero_mask", "inactive_commands", "unmasked_data"} <= self.ignored,
            pre_edge_and_held_checks_per_item=self.pre_checks == self.held_checks == self.checks,
            random_cycles=self.random_checks == config.random_cycles,
        )
        return dict(status="PASS" if all(goals.values()) else "FAIL", parameters=config.parameters, seed=config.seed,
                    checked_transactions=self.checks, pre_edge_checks=self.pre_checks, held_checks=self.held_checks,
                    random_transactions=self.random_checks, structural_assertions="PASS" if config.check_internals else "NOT_RUN", goals=goals,
                    bins=dict(entries={key: sorted(value) for key, value in self.entries.items()}, reads=sorted(self.reads),
                    unknown_addresses=sorted(self.unknowns), unused_addresses=sorted(self.invalids), mask_populations=sorted(self.populations),
                    written_slices=sorted(self.slices), operation_classes=sorted(self.classes), reset_operation_classes=sorted(self.reset_classes),
                    address_relations=sorted(self.relations), read_port_pairs=sorted(self.read_pairs), patterns=sorted(self.patterns),
                    ignored_cases=sorted(self.ignored), expected_assertions=dict(self.violations), waveform_transitions=dict(self.transitions)),
                    waivers=dict(depth_one_different_addresses=config.depth == 1, single_slice_partial_mask=config.slices == 1,
                                 raw_mode_disabled=not config.raw, single_read_port_pairs=config.read_ports == 1))
