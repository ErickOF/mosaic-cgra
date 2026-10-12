"""Directed and seeded priority_encoder sequences."""

from itertools import combinations, product
import os
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from priority_encoder.model import expected_outputs
from priority_encoder.transaction import PriorityEncoderItem


class PriorityEncoderSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("priority_encoder_sequence")
        self.config = config

    async def send(self, label, request, *, hold_ns=0.001, expect_ambiguity=True):
        ambiguous = expected_outputs(self.config, bits(request, self.config.width)).ambiguous
        item = PriorityEncoderItem(label, request, expected_ambiguity=expect_ambiguity and ambiguous, hold_ns=hold_ns)
        await self.start_item(item)
        await self.finish_item(item)

    async def body(self):
        config = self.config
        probe = os.getenv("PRIORITY_ENCODER_AMBIGUITY_PROBE", "")
        if probe:
            assert probe in "xz" and len(probe) == 1 and config.width == 4 and config.lsb_high_priority
            await self.send("unexpected_ambiguous_request", f"001{probe}", expect_ambiguity=False)
            return
        await self.send("no_request", 0, hold_ns=1)
        for index in range(config.width):
            await self.send("single_request", 1 << index, hold_ns=1)
            await self.send("return_to_none", 0)
        for low, high in combinations(range(config.width), 2):
            await self.send("request_pair", (1 << low) | (1 << high))
        await self.send("all_requests", config.maximum, hold_ns=1)
        for low in range(config.width):
            for high in range(low, config.width):
                await self.send("contiguous_requests", ((1 << (high - low + 1)) - 1) << low)
        for pattern in ("01", "10"):
            await self.send("alternating_requests", int((pattern * config.width)[:config.width], 2))
        for index, population in sorted(config.population_cross):
            lower = [other for other in range(config.width) if config.higher(index, other)]
            request = (1 << index) | sum(1 << other for other in lower[:population - 1])
            await self.send("selected_population_cross", request)
        for before, after in product(range(config.width), repeat=2):
            await self.send("winner_transition_before", 1 << before)
            await self.send("winner_transition_after", 1 << after)

        # An unknown best request may outrank a known request at the other end.
        # Check this explicit fail-open case before masked lower-bit activity.
        for state in "xz":
            word = ["0"] * config.width
            highest = 0 if config.lsb_high_priority else config.width - 1
            if config.width > 1:
                word[highest] = "1"  # Opposite end in the MSB-first string.
            word[config.width - highest - 1] = state
            await self.send("unknown_highest_priority", "".join(word))

        # Known highest requests remain winners when lower bits become X/Z.
        # Their multiple flag can still become unknown; it is checked separately.
        for winner, other in product(range(config.width), repeat=2):
            if not config.higher(winner, other):
                continue
            for state in "01xz":
                await self.send("masked_activity_before", 1 << winner)
                word = list(bits(1 << winner, config.width))
                word[config.width - other - 1] = state
                await self.send("masked_activity_after", "".join(word))
        for bit, state in product(range(config.width), "xz"):
            word = ["0"] * config.width
            word[config.width - bit - 1] = state
            await self.send("single_unknown_request", "".join(word))
            for known in range(config.width):
                if known == bit:
                    continue
                pair = word.copy()
                pair[config.width - known - 1] = "1"
                await self.send("unknown_known_pair", "".join(pair))
                await self.send("known_recovery", 1 << known)
        for bit, background, before, after in product(range(config.width), "01", "01xz", "01xz"):
            old, new = [background] * config.width, [background] * config.width
            old[config.width - bit - 1], new[config.width - bit - 1] = before, after
            await self.send("bit_transition_before", "".join(old))
            await self.send("bit_transition_after", "".join(new))
        for word in ("x" * config.width, "z" * config.width, ("xz" * config.width)[:config.width]):
            await self.send("fully_unknown_requests", word)
            await self.send("recover_none", 0)
        if config.width <= 8:
            for request in range(config.maximum + 1):
                await self.send("exhaustive_binary", request)
        if config.width <= 5:
            for word in product("01xz", repeat=config.width):
                await self.send("exhaustive_four_state", "".join(word))

        rng = random.Random(config.seed)
        for index in range(config.random_cycles):
            if index % 16 == 0:
                request = 0
            elif index % 16 == 1:
                request = 1 << rng.randrange(config.width)
            elif index % 16 == 2:
                request = config.maximum
            elif index % 4 == 3:
                request = "".join(rng.choice("01xz") for _ in range(config.width))
            else:
                request = rng.getrandbits(config.width)
            await self.send(f"random_{index}", request)
        await self.send("final_none", 0, hold_ns=1)
