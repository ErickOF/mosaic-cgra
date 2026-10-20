"""Directed graph/temporal scenarios and seeded legal/illegal scheduled operations."""

from itertools import combinations, product
import random
from pyuvm import uvm_sequence

from mosaic_uvm.logic import bits
from bypass_network.transaction import BypassNetworkItem, pack, unpack


class BypassNetworkSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("bypass_network_sequence")
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = dict(i_clk="0", i_rstb="0", i_flush="0",
                          i_source_data="0" * (config.width * config.sources), i_source_valid="0" * config.sources,
                          i_destination_enable="0" * config.destinations,
                          i_select=pack((config.connected(destination)[0] for destination in range(config.destinations)), config.select_width),
                          i_capture_enable="0" * config.destinations)

    def expected_selections(self):
        """Acknowledge intentional selection violations; other illegal inputs fail."""
        config, ports = self.config, self.ports
        found = set()
        selects = unpack(ports["i_select"], config.select_width)
        for destination, select in enumerate(selects):
            enabled = ports["i_destination_enable"][-1 - destination] == "1"
            captured = not config.registered or ports["i_capture_enable"][-1 - destination] == "1"
            if not enabled or not captured:
                continue
            if set(select) & {"x", "z"}:
                found.add(f"unknown_select:{destination}")
            else:
                source = int(select, 2)
                if source >= config.sources:
                    found.add(f"out_of_range:{destination}")
                elif source not in config.connected(destination):
                    found.add(f"disconnected:{destination}")
        return found

    async def send(self, label, *, acknowledge=True, hold_ps=10, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, len(self.ports[name]))
        item = BypassNetworkItem(label, self.ports, violations=self.expected_selections() if acknowledge else (),
                                 hold_ps=hold_ps, random=random)
        await self.start_item(item)
        await self.finish_item(item)

    async def cycle(self, label, *, random=False, acknowledge=True, hold_ps=10, **changes):
        await self.send(f"{label}:prepare", i_clk=0, acknowledge=acknowledge, hold_ps=hold_ps, **changes)
        await self.send(label, i_clk=1, acknowledge=acknowledge, hold_ps=hold_ps, random=random)

    def words(self):
        return tuple(self.rng.getrandbits(self.config.width) for _ in range(self.config.sources))

    def defaults(self):
        config = self.config
        return dict(i_rstb=1, i_flush=0, i_destination_enable="1" * config.destinations,
                    i_capture_enable="1" * config.destinations, i_source_valid="1" * config.sources,
                    i_select=pack((config.connected(destination)[0] for destination in range(config.destinations)), config.select_width),
                    i_source_data=pack(self.words(), config.width))

    async def initialize(self):
        await self.cycle("reset", i_rstb=0, i_flush=0, i_destination_enable=0, i_capture_enable=0)
        await self.send("release", i_clk=0, i_rstb=1)

    def isolated(self, destination, source, word, *, enable=1, capture=1, valid=1):
        config = self.config
        words = list(self.words())
        if source < config.sources:
            words[source] = word
        selects = [config.connected(index)[0] for index in range(config.destinations)]
        selects[destination] = source
        validity = [1] * config.sources
        if source < config.sources:
            validity[source] = valid
        return dict(i_rstb=1, i_flush=0, i_source_data=pack(words, config.width), i_source_valid=pack(validity, 1),
                    i_destination_enable=enable << destination, i_capture_enable=capture << destination,
                    i_select=pack(selects, config.select_width))

    async def edges_and_patterns(self):
        config = self.config
        maximum = (1 << config.width) - 1
        patterns = {0, maximum, maximum ^ 1, int(("01" * config.width)[:config.width], 2), int(("10" * config.width)[:config.width], 2)}
        patterns.update(1 << bit for bit in range(config.width))
        if config.width <= 2:
            patterns.update(range(maximum + 1))
        for destination, source in sorted(config.edges):
            for word in sorted(patterns):
                await self.cycle("edge_pattern", **self.isolated(destination, source, word))
            for enable, capture, valid in product((0, 1), repeat=3):
                await self.cycle("control_cross", **self.isolated(destination, source, maximum,
                                                                  enable=enable, capture=capture, valid=valid))
            for value in "xz":
                await self.cycle("invalid_payload", **self.isolated(destination, source, value * config.width, valid=0))
            await self.cycle("unselected_prime", **self.isolated(destination, source, maximum))
            for other in range(config.sources):
                if other == source:
                    continue
                for value in "01xz":
                    words = [0] * config.sources
                    words[source], words[other] = maximum, value * config.width
                    valid = [1] * config.sources
                    valid[other] = value
                    await self.cycle(f"unselected:{destination}:{source}:{other}:{value}",
                                     i_source_data=pack(words, config.width), i_source_valid=pack(valid, 1),
                                     i_capture_enable=0 if config.registered else 1 << destination)

    async def illegal_selections(self):
        config = self.config
        for destination in range(config.destinations):
            encodings = tuple(source for source in range(config.sources) if (destination, source) in config.disconnected)
            encodings += tuple(range(config.sources, 1 << config.select_width))
            for source in encodings:
                await self.cycle("illegal_known", **self.isolated(destination, source, 0))
            for select in config.unknown_selects:
                changes = self.isolated(destination, 0, 0)
                changes["i_source_data"] = 0
                selections = [config.connected(index)[0] for index in range(config.destinations)]
                selections[destination] = select
                changes["i_select"] = pack(selections, config.select_width)
                await self.cycle("illegal_unknown", **changes)

    async def independence(self):
        config = self.config
        for population in range(1, config.maximum_fanout + 1):
            source = max(range(config.sources), key=lambda candidate: sum((destination, candidate) in config.edges for destination in range(config.destinations)))
            destinations = [destination for destination in range(config.destinations) if (destination, source) in config.edges][:population]
            for valid in (0, 1):
                await self.cycle("fanout", **(self.defaults() | dict(
                    i_select=pack((source,) * config.destinations, config.select_width),
                    i_destination_enable=sum(1 << destination for destination in destinations),
                    i_source_valid=("1" if valid else "0") * config.sources)))
        matching = sorted(config.distinct_assignment().items())
        for population in range(1, len(matching) + 1):
            selected = [config.connected(destination)[0] for destination in range(config.destinations)]
            for destination, source in matching[:population]:
                selected[destination] = source
            await self.cycle("distinct_sources", **(self.defaults() | dict(
                i_select=pack(selected, config.select_width), i_destination_enable=sum(1 << destination for destination, _ in matching[:population]))))
        for first, second in combinations(range(config.destinations), 2):
            for source1, source2 in product(config.connected(first), config.connected(second)):
                selected = [config.connected(destination)[0] for destination in range(config.destinations)]
                selected[first], selected[second] = source1, source2
                await self.cycle("destination_pair", **(self.defaults() | dict(i_select=pack(selected, config.select_width))))

    async def timing_and_contexts(self):
        config = self.config
        await self.cycle("timing_prime", **self.defaults())
        if not config.registered:
            for field, port, width in (("rstb", "i_rstb", 1), ("flush", "i_flush", 1), ("capture", "i_capture_enable", config.destinations)):
                for value in "01xz":
                    await self.send(f"ignored:{field}", **{port: value * width}, hold_ps=1000)
            await self.cycle("restore_controls", **self.defaults())
            return
        await self.cycle("ignored:held_select", i_capture_enable=0, i_select="x" * (config.destinations * config.select_width),
                         i_source_data="x" * (config.sources * config.width), i_source_valid="z" * config.sources, hold_ps=1000)
        await self.cycle("ignored:disabled_capture", i_destination_enable=0, i_capture_enable="z" * config.destinations, hold_ps=1000)
        for reset, flush, capture in product((0, 1), repeat=3):
            await self.cycle("priority_prime", **self.defaults())
            await self.cycle("priority", i_rstb=reset, i_flush=flush, i_capture_enable=("1" if capture else "0") * config.destinations,
                             i_source_data=pack(self.words(), config.width))
        for state in ("valid", "invalid", *(("mixed",) if config.destinations > 1 else ())):
            await self.cycle("context_prime", **self.defaults())
            if state != "valid":
                await self.cycle("context_invalidate", i_source_valid=0, i_capture_enable=1 if state == "mixed" else (1 << config.destinations) - 1)
            await self.cycle(f"context:{state}", i_flush=1, i_capture_enable="1" * config.destinations)
            await self.cycle("context_new_capture", **self.defaults())
        # Selection and data can change throughout a scheduled hold without
        # altering saved state or reporting a stale selection error.
        for _ in range(8):
            await self.cycle("prolonged_hold", i_capture_enable=0, i_source_data=pack(self.words(), config.width),
                             i_select=self.rng.getrandbits(config.destinations * config.select_width), hold_ps=1000)

    async def probe(self):
        config = self.config
        await self.initialize()
        await self.cycle("probe_prime", **self.isolated(0, config.connected(0)[0], (1 << config.width) - 1))
        name, value = config.probe.split(":")
        changes = {}
        if name in ("i_rstb", "i_flush"):
            changes[name] = value
        elif name == "destination_enable":
            changes["i_destination_enable"] = pack([value] + [0] * (config.destinations - 1), 1)
        elif name == "capture_enable":
            changes["i_capture_enable"] = pack([value] + [0] * (config.destinations - 1), 1)
        elif name == "source_valid":
            valid = [1] * config.sources
            valid[config.connected(0)[0]] = value
            changes["i_source_valid"] = pack(valid, 1)
        elif name == "source_data":
            words = list(self.words())
            words[config.connected(0)[0]] = value * config.width
            changes["i_source_data"] = pack(words, config.width)
        else:
            selections = [config.connected(destination)[0] for destination in range(config.destinations)]
            selections[0] = (next(source for destination, source in sorted(config.disconnected) if destination == 0)
                             if name == "disconnected" else config.sources if name == "out_of_range" else value * config.select_width)
            changes["i_select"] = pack(selections, config.select_width)
        await self.cycle("untagged_illegal_request", acknowledge=False, **changes)
        raise AssertionError("Illegal stimulus did not trigger its live protocol assertion")

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.initialize()
        await self.edges_and_patterns()
        await self.illegal_selections()
        await self.independence()
        await self.timing_and_contexts()
        config = self.config
        for index in range(config.random_cycles):
            valid = self.rng.getrandbits(config.sources)
            words = [self.rng.getrandbits(config.width) if valid >> source & 1 else self.rng.choice(("x", "z")) * config.width for source in range(config.sources)]
            selections = [self.rng.choice(config.unknown_selects) if self.rng.random() < 0.1 else self.rng.randrange(1 << config.select_width) for _ in range(config.destinations)]
            await self.cycle(f"random_{index}", random=True,
                             i_rstb=int(self.rng.random() >= 0.03), i_flush=int(self.rng.random() < 0.05),
                             i_source_data=pack(words, config.width), i_source_valid=valid,
                             i_destination_enable=self.rng.getrandbits(config.destinations),
                             i_capture_enable=self.rng.getrandbits(config.destinations), i_select=pack(selections, config.select_width))
        await self.cycle("final_flush", i_rstb=1, i_flush=1, i_destination_enable=0, i_capture_enable=0, hold_ps=1000)
