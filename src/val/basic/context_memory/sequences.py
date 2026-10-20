"""Context lifecycle, partial assembly, collision boundaries, and seeded traffic."""

from itertools import combinations, product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from context_memory.coverage import legal_classes
from context_memory.transaction import ContextMemoryItem, pack, unpack


class ContextMemorySequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("context_memory_sequence")
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = dict(i_clk="0", i_rstb="0", i_read_enable="0" * config.read_ports,
                          i_read_raw="0" * config.read_ports, i_read_address="0" * (config.read_ports * config.address_width),
                          i_write_enable="0", i_write_mask="0" * config.slices, i_write_address="0" * config.address_width,
                          i_write_data="0" * config.width, i_commit_enable="0", i_commit_address="0" * config.address_width,
                          i_invalidate_enable="0", i_invalidate_address="0" * config.address_width)

    def expected_bad_addresses(self):
        config, ports = self.config, self.ports
        found = set()
        for kind in ("write", "commit", "invalidate"):
            active = ports[f"i_{kind}_enable"] == "1" and (kind != "write" or "1" in ports["i_write_mask"])
            value = ports[f"i_{kind}_address"]
            if active and (set(value) & {"x", "z"} or int(value, 2) >= config.depth):
                found.add(kind + "_address")
        for port, (enabled, value) in enumerate(zip(unpack(ports["i_read_enable"], 1), unpack(ports["i_read_address"], config.address_width))):
            if enabled == "1" and (set(value) & {"x", "z"} or int(value, 2) >= config.depth):
                found.add(f"read_address:{port}")
        return found

    async def send(self, label, *, acknowledge=True, hold_ps=10, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, len(self.ports[name]))
        item = ContextMemoryItem(label, self.ports, violations=self.expected_bad_addresses() if acknowledge else (),
                                 hold_ps=hold_ps, random=random)
        await self.start_item(item)
        await self.finish_item(item)

    async def cycle(self, label, *, random=False, acknowledge=True, **changes):
        await self.send(label + ":prepare", i_clk=0, acknowledge=acknowledge, **changes)
        await self.send(label, i_clk=1, acknowledge=acknowledge, random=random)

    def idle(self):
        return dict(i_rstb=1, i_write_enable=0, i_commit_enable=0, i_invalidate_enable=0)

    def read(self, index, *, raw=0):
        return dict(i_read_enable=(1 << self.config.read_ports) - 1,
                    i_read_address=pack((index,) * self.config.read_ports, self.config.address_width),
                    i_read_raw=("1" if raw and self.config.raw else "0") * self.config.read_ports)

    async def initialize(self):
        await self.cycle("reset", **(self.idle() | dict(i_rstb=0, i_read_enable=0, i_read_raw=0)))
        await self.send("release", i_clk=0, i_rstb=1)

    async def load(self, index, *, commit=1, word=None):
        word = self.rng.getrandbits(self.config.width) if word is None else word
        await self.cycle("load", **(self.idle() | self.read(index) | dict(i_write_enable=1, i_write_mask=(1 << self.config.slices) - 1,
            i_write_address=index, i_write_data=word, i_commit_enable=commit, i_commit_address=index)))

    async def lifecycle(self):
        config = self.config
        maximum = (1 << config.width) - 1
        patterns = {0, maximum, maximum ^ 1, int(("01" * config.width)[:config.width], 2)} | {1 << bit for bit in range(config.width)}
        for index in range(config.depth):
            await self.cycle("invalidate", **(self.idle() | self.read(index) | dict(i_invalidate_enable=1, i_invalidate_address=index)))
            # Initially unreset data can be inspected raw while validity is low.
            for raw in ((0, 1) if config.raw else (0,)):
                await self.cycle("uncommitted_read", **(self.idle() | self.read(index, raw=raw)))
            for slice_index in range(config.slices):
                word = self.rng.getrandbits(config.width)
                await self.cycle("partial_assembly", **(self.idle() | self.read(index, raw=1) | dict(
                    i_write_enable=1, i_write_address=index, i_write_mask=1 << slice_index, i_write_data=word,
                    i_commit_enable=int(slice_index == config.slices - 1), i_commit_address=index)))
            for raw in ((0, 1) if config.raw else (0,)):
                await self.cycle("committed_read", **(self.idle() | self.read(index, raw=raw)))
            for word in sorted(patterns):
                await self.load(index, word=word)
            await self.load(index, commit=0)
            await self.cycle("commit_only", **(self.idle() | self.read(index) | dict(i_commit_enable=1, i_commit_address=index)))
            await self.cycle("write_invalidate", **(self.idle() | self.read(index, raw=1) | dict(
                i_write_enable=1, i_write_address=index, i_write_mask=1, i_write_data=maximum,
                i_invalidate_enable=1, i_invalidate_address=index)))

    async def masks_and_priorities(self):
        config = self.config
        for previous, population in product((0, 1), range(config.slices + 1)):
            await self.load(0)
            if not previous:
                await self.cycle("prior_invalid", **(self.idle() | dict(i_invalidate_enable=1, i_invalidate_address=0)))
            await self.cycle("mask_population", **(self.idle() | self.read(0, raw=1) | dict(i_write_enable=1,
                i_write_address=0, i_write_mask=(1 << population) - 1, i_write_data=self.rng.getrandbits(config.width))))
        patterns = (0, (1 << config.width) - 1, 1, ((1 << config.width) - 1) ^ 1, int(("01" * config.width)[:config.width], 2))
        masks = (0, (1 << config.slices) - 1, *((1,) if config.slices > 1 else ()))
        for word, mask in product(patterns, masks):
            await self.cycle("pattern_mask", **(self.idle() | dict(i_write_enable=1, i_write_address=0, i_write_mask=mask, i_write_data=word)))
        for flags in sorted(legal_classes(config.depth)):
            for reset in (1, 0):
                await self.load(0)
                other = int(config.depth > 1)
                if other:
                    await self.load(other)
                for raw in ((0, 1) if config.raw else (0,)):
                    await self.cycle("operation_priority", **(self.idle() | self.read(0, raw=raw) | dict(i_rstb=reset,
                        i_write_enable=flags[0], i_write_mask=1, i_write_address=0, i_write_data=self.rng.getrandbits(config.width),
                        i_commit_enable=flags[1], i_commit_address=0, i_invalidate_enable=flags[2],
                        i_invalidate_address=other if flags[1] else 0)))
                if config.depth > 1:
                    await self.cycle("different_addresses", **(self.idle() | self.read(other) | dict(i_write_enable=flags[0],
                        i_write_mask=1, i_write_address=0, i_write_data=self.rng.getrandbits(config.width),
                        i_commit_enable=flags[1], i_commit_address=other, i_invalidate_enable=flags[2], i_invalidate_address=0)))

    async def address_and_ignore_cases(self):
        config = self.config
        await self.load(0)
        for port in range(config.read_ports):
            for value in (*range(config.depth, 1 << config.address_width), *config.unknown_addresses):
                indices = [0] * config.read_ports
                indices[port] = value
                await self.cycle("illegal_read", **(self.idle() | dict(i_read_enable=1 << port,
                    i_read_raw=0, i_read_address=pack(indices, config.address_width))))
        for kind in ("write", "commit", "invalidate"):
            for value in (*range(config.depth, 1 << config.address_width), *config.unknown_addresses):
                await self.cycle("illegal_command", **(self.idle() | self.read(0, raw=1) | dict(
                    **{f"i_{kind}_enable": 1, f"i_{kind}_address": value}, i_write_mask=1, i_write_data=1)))
        await self.cycle("ignored:disabled_reads", **(self.idle() | dict(i_read_enable=0,
            i_read_address="x" * (config.read_ports * config.address_width), i_read_raw=("z" if config.raw else "0") * config.read_ports)))
        await self.cycle("ignored:zero_mask", **(self.idle() | self.read(0) | dict(i_write_enable=1, i_write_mask=0,
            i_write_address="z" * config.address_width, i_write_data="x" * config.width)))
        await self.cycle("ignored:inactive_commands", **(self.idle() | dict(
            i_write_address="x" * config.address_width, i_commit_address="z" * config.address_width,
            i_invalidate_address="x" * config.address_width, i_write_mask="z" * config.slices, i_write_data="z" * config.width)))
        # Only one data slice is consumed; unknown bits in every other slice
        # must neither propagate into storage nor prevent a legal update.
        data = ["z" * config.slice_width] * config.slices
        data[0] = "1" * config.slice_width
        await self.cycle("ignored:unmasked_data", **(self.idle() | self.read(0, raw=1) | dict(
            i_write_enable=1, i_write_address=0, i_write_mask=1, i_write_data=pack(data, config.slice_width))))
        for first, second in combinations(range(config.read_ports), 2):
            for index1, index2 in product(range(config.depth), repeat=2):
                indices = [0] * config.read_ports
                indices[first], indices[second] = index1, index2
                await self.send("read_port_pair", **(self.idle() | dict(i_read_enable=(1 << first) | (1 << second),
                    i_read_address=pack(indices, config.address_width), i_read_raw=0)), hold_ps=1000)

    async def probe(self):
        config = self.config
        name, value = config.probe.split(":")
        await self.initialize()
        if name != "commit_data_unknown":
            for index in range(config.depth):
                await self.load(index)
        changes = self.idle() | self.read(0)
        if name == "commit_data_unknown":
            changes |= dict(i_commit_enable=1, i_commit_address=0)
        elif name == "commit_invalidate_collision":
            changes |= dict(i_commit_enable=1, i_commit_address=0, i_invalidate_enable=1, i_invalidate_address=0)
        elif name in ("write_data", "write_mask"):
            changes |= dict(i_write_enable=1, i_write_address=0, i_write_mask=(1 << config.slices) - 1, i_write_data=0)
            changes["i_" + name] = value * (config.width if name == "write_data" else config.slices)
        elif name.endswith("_address"):
            kind = name.removesuffix("_address")
            index = config.depth if value == "range" else value * config.address_width
            if kind == "read":
                changes["i_read_address"] = pack([index] + [0] * (config.read_ports - 1), config.address_width)
            else:
                changes |= {f"i_{kind}_enable": 1, f"i_{kind}_address": index, "i_write_mask": 1, "i_write_data": 1}
        elif name in ("read_raw", "read_enable", "raw_forbidden"):
            changes["i_read_raw" if name == "raw_forbidden" else "i_" + name] = pack([value] + [0] * (config.read_ports - 1), 1)
        else:
            changes[name if name == "i_rstb" else "i_" + name] = value
        await self.cycle("untagged_illegal", acknowledge=False, **changes)
        raise AssertionError("Illegal stimulus did not trigger its live assertion")

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.initialize()
        await self.lifecycle()
        await self.masks_and_priorities()
        await self.address_and_ignore_cases()
        config = self.config
        # Seed every word so randomized commits never rely on unknown reset data.
        for index in range(config.depth):
            await self.load(index)
        for index in range(config.random_cycles):
            write, commit, invalidate = (self.rng.randrange(config.depth) for _ in range(3))
            enables = [self.rng.randrange(2) for _ in range(3)]
            if commit == invalidate and enables[1] and enables[2]:
                enables[2] = 0
            await self.cycle(f"random_{index}", random=True, i_rstb=int(self.rng.random() >= 0.03),
                i_write_enable=enables[0], i_write_mask=self.rng.getrandbits(config.slices), i_write_address=write,
                i_write_data=self.rng.getrandbits(config.width), i_commit_enable=enables[1], i_commit_address=commit,
                i_invalidate_enable=enables[2], i_invalidate_address=invalidate,
                i_read_enable=self.rng.getrandbits(config.read_ports), i_read_raw=self.rng.getrandbits(config.read_ports) if config.raw else 0,
                i_read_address=pack((self.rng.randrange(config.depth) for _ in range(config.read_ports)), config.address_width))
        await self.send("final_idle", **self.idle(), hold_ps=1000)
