"""Directed and seeded sequences mapped to the MOSAIC write gate specification."""

from __future__ import annotations

from itertools import product
import os
import random

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_sequence, uvm_test

from write_gate_env import (
    Inputs, WriteGateConfig, WriteGateEnv, WriteGateItem, bits,
)


class WriteGateSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("write_gate_sequence")
        self.config = config
        self.rng = random.Random(config.seed)
        self.state = {"register": [0], "memory": [0] * 4}

    async def send(self, label, write, suppress, *, hold_ns=0.001, acknowledge=True, **destination):
        # Explicitly acknowledge illegal four-state stimulus in positive tests.
        # The assertion still executes; untagged probes must fail before coverage.
        w, s = bits(write, self.config.width), bits(suppress, self.config.width)
        expected = set()
        if acknowledge:
            if "x" in w or "z" in w:
                expected.add("unknown_write_enable")
            if any(request != "0" and control in "xz" for request, control in zip(w, s, strict=True)):
                expected.add("unknown_requested_suppression")
        item = WriteGateItem(label, Inputs(write, suppress, **destination), expected_violations=expected, hold_ns=hold_ns)
        await self.start_item(item)
        await self.finish_item(item)
        if self.config.integration and item.inputs.protocol == "accepted":
            dest = item.inputs.destination
            address = item.inputs.address if dest == "memory" else 0
            old = self.state[dest][address]
            self.state[dest][address] = (old & (self.config.maximum ^ write)) | (item.inputs.data & write)

    async def functional(self):
        config, maximum = self.config, self.config.maximum
        probe = os.getenv("WRITE_GATE_CONTROL_PROBE", "")
        if probe:
            assert probe in ("write_x", "write_z", "suppress_x", "suppress_z")
            field, state = probe.split("_")
            await self.send("unexpected_unknown_control", state * config.width if field == "write" else maximum,
                            state * config.width if field == "suppress" else 0, acknowledge=False)
            return
        basis = sorted({0, maximum, 1, maximum ^ 1,
                        int(("01" * config.width)[:config.width], 2),
                        int(("10" * config.width)[:config.width], 2)})
        for write, suppress in product(basis, repeat=2):
            await self.send("mask_pattern_cross", write, suppress)
            await self.send("repeat_mask", write, suppress)
        for bit in range(config.width):
            one = 1 << bit
            for write, suppress in ((one, 0), (one, one), (maximum, one), (maximum ^ one, maximum)):
                await self.send("independent_bit", write, suppress)
            for w, s in product("01xz", repeat=2):
                write, suppress = ["0"] * config.width, ["1"] * config.width
                write[config.width - bit - 1], suppress[config.width - bit - 1] = w, s
                await self.send("independent_four_state_bit", "".join(write), "".join(suppress))
            for old_w, old_s, new_w, new_s in product((0, 1), repeat=4):
                await self.send("transition_before", old_w * one, old_s * one)
                await self.send("transition_after", new_w * one, new_s * one)
            for suppress in (0, one, 0, one, 0):
                await self.send("back_to_back_permit_suppress", one, suppress)
        for population in range(config.width + 1):
            await self.send("suppression_ratio", maximum, (1 << population) - 1)
        if config.width <= 4:
            for write, suppress in product(range(maximum + 1), repeat=2):
                await self.send("exhaustive_binary", write, suppress)
        if config.width <= 2:
            words = ["".join(word) for word in product("01xz", repeat=config.width)]
            for write, suppress in product(words, repeat=2):
                await self.send("exhaustive_four_state", write, suppress)
        for w, s in product("01xz", repeat=2):
            await self.send("all_four_state_masks", w * config.width, s * config.width)
        for write, suppress in ((0, 0), (maximum, 0), (maximum, maximum)):
            for _ in range(32):
                await self.send("long_idle_or_write_interval", write, suppress, hold_ns=1)
        # Both inputs changing together and either input changing alone.
        for write, suppress in ((0, 0), (maximum, maximum), (0, 0), (0, maximum), (maximum, maximum), (maximum, 0)):
            await self.send("simultaneous_and_independent", write, suppress)
        for index in range(config.random_cycles):
            write, suppress = self.rng.getrandbits(config.width), self.rng.getrandbits(config.width)
            if index % 7 == 0:
                write = "".join(self.rng.choice("01xz") for _ in range(config.width))
                suppress = "".join(self.rng.choice("01xz") for _ in range(config.width))
            elif index % 7 == 1:
                word = list(bits(suppress, config.width))
                word[self.rng.randrange(config.width)] = self.rng.choice("xz")
                suppress = "".join(word)
            await self.send(f"random_{index}", write, suppress)

    async def destination_write(self, label, destination, address, write, data, *, reason="none", protocol=None, hold_ns=0.001):
        prior = self.state[destination][address if destination == "memory" else 0]
        protocol = protocol or ("accepted" if write else "idle")
        suppress = (write & (self.config.maximum ^ (prior ^ data)) if reason == "redundant_value"
                    else write if reason == "inactive_destination" else 0)
        await self.send(label, write, suppress, data=data, destination=destination, address=address,
                        protocol=protocol, reason=reason, hold_ns=hold_ns)

    async def integration(self):
        config, maximum = self.config, self.config.maximum
        if os.getenv("WRITE_GATE_INTEGRATION_PROBE", ""):
            assert os.environ["WRITE_GATE_INTEGRATION_PROBE"] == "unsafe_suppression"
            await self.send("unsafe_accepted_write", 1, 1, data=1, reason="redundant_value")
            return
        for dest in ("register", "memory"):
            for address in range(4) if dest == "memory" else (0,):
                await self.destination_write("idle", dest, address, 0, 0)
                await self.send("idle_with_suppression", 0, maximum, data=0, destination=dest,
                                address=address, protocol="idle", reason="redundant_value")
                await self.destination_write("baseline_write", dest, address, maximum, maximum)
                await self.destination_write("fully_redundant", dest, address, maximum, maximum, reason="redundant_value")
                if config.width > 1:
                    await self.destination_write("partly_redundant", dest, address, maximum, maximum ^ 1, reason="redundant_value")
                await self.destination_write("required_change", dest, address, maximum, 0, reason="redundant_value")
                # Cancellation occurs before destination acceptance. No response
                # or post-acceptance rollback is provided by this fixture.
                await self.destination_write("cancel_permitted", dest, address, maximum, maximum, protocol="cancelled")
                await self.destination_write("cancel_suppressed", dest, address, maximum, 0, reason="redundant_value", protocol="cancelled")
                if config.width > 1:
                    await self.destination_write("cancel_mixed", dest, address, maximum, 1, reason="redundant_value", protocol="cancelled")
                await self.destination_write("inactive_destination", dest, address, maximum, maximum,
                                             reason="inactive_destination", protocol="cancelled")
                for bit in range(config.width):
                    await self.destination_write("masked_bit_change", dest, address, 1 << bit, maximum)
                    await self.destination_write("masked_bit_redundant", dest, address, 1 << bit, maximum, reason="redundant_value")
                    await self.destination_write("masked_bit_return", dest, address, 1 << bit, 0, reason="redundant_value")
            for _ in range(32):
                await self.destination_write("long_no_write", dest, 0, 0, maximum, hold_ns=1)
                await self.destination_write("long_suppression", dest, 0, maximum, self.state[dest][0],
                                             reason="redundant_value", hold_ns=1)
        for index in range(config.random_cycles):
            dest = "register" if index % 2 == 0 else "memory"
            address = self.rng.randrange(4) if dest == "memory" else 0
            prior = self.state[dest][address]
            write = self.rng.getrandbits(config.width)
            data = prior if index % 5 == 0 else self.rng.getrandbits(config.width)
            reason = self.rng.choice(("none", "redundant_value", "redundant_value", "inactive_destination"))
            protocol = "cancelled" if reason == "inactive_destination" or index % 11 == 0 else None
            await self.destination_write(f"random_{index}", dest, address, write, data, reason=reason, protocol=protocol)

    async def body(self):
        if self.config.integration:
            await self.integration()
        else:
            await self.functional()


@test(timeout_time=1, timeout_unit="ms")
class WriteGateTest(uvm_test):
    def build_phase(self):
        self.config = WriteGateConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        for name in ("i_write_enable", "i_suppress", "o_write_enable", "o_write_suppressed"):
            assert len(getattr(cocotb.top, name)) == self.config.width, f"Wrong width for {name}"
        if self.config.integration:
            assert len(cocotb.top.i_write_data) == len(cocotb.top.o_register_state) == self.config.width
            assert len(cocotb.top.o_memory_state) == 4 * self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "quiet": False, "capture_window": False, "sample": Event()})
        self.env = WriteGateEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_write_enable.value = 0
        cocotb.top.i_suppress.value = 0
        if self.config.integration:
            cocotb.top.i_clk.value = 0
            cocotb.top.i_rstb.value = 0
            cocotb.top.i_capture_valid.value = 0
            cocotb.top.i_destination.value = 0
            cocotb.top.i_address.value = 0
            cocotb.top.i_write_data.value = 0
            await Timer(1, unit="ps")
            cocotb.top.i_clk.value = 1
            await Timer(1, unit="ps")
            cocotb.top.i_clk.value = 0
            cocotb.top.i_rstb.value = 1
        await WriteGateSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
