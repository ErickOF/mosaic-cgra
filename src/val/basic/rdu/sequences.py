"""Directed delay histories, ownership boundaries and seeded scheduled traffic."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from rdu.config import STALL_LIMIT
from rdu.model import fields, pack
from rdu.transaction import INPUTS, RduItem


class RduSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('rdu_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*config.widths[name] for name in INPUTS}
        self.all_channels = (1 << config.channels)-1
        self.maximum_delay = max(config.capacities)
        self.maximum_data = (1 << config.width)-1
        self.last = None

    async def send(self, label, *, edge=True, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = RduItem(label, self.ports, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.observation
        return item

    def data(self):
        return pack([self.rng.getrandbits(self.config.width) for _ in range(self.config.channels)], self.config.width)

    def delays(self):
        return [int(word, 2) for word in fields(self.ports['i_delay'], self.config.delay_width)]

    async def reset(self, *, delays=None):
        await self.send('reset_priority', i_rstb=0, i_advance=1, i_channel_enable=self.all_channels,
            i_delay=pack(delays or [0]*self.config.channels, self.config.delay_width),
            i_input_data=self.data(), i_input_valid=self.all_channels, i_flush=self.all_channels)
        await self.send('release', edge=False, i_rstb=1, i_advance=0, i_input_valid=0, i_flush=0)

    async def configure(self, delays):
        await self.send('flush_reconfigure', i_rstb=1, i_flush=self.all_channels, i_advance=0,
            i_channel_enable=self.all_channels, i_delay=pack(delays, self.config.delay_width), i_input_valid=0)
        await self.send('flush_release', edge=False, i_flush=0)

    async def fill(self, count):
        for _ in range(count):
            await self.send('fill_tokens', i_advance=1, i_input_valid=self.all_channels, i_input_data=self.data())

    async def drain(self):
        for _ in range(self.maximum_delay+1):
            await self.send('drain_bubbles', i_rstb=1, i_advance=1, i_flush=0,
                i_channel_enable=self.all_channels, i_input_valid=0,
                i_input_data='x'*self.config.widths['i_input_data'])

    async def all_delays(self):
        config = self.config
        patterns = [0, self.maximum_data, self.maximum_data//3, self.maximum_data ^ (self.maximum_data//3)]
        patterns += [1 << bit for bit in range(config.width)]
        patterns += [self.maximum_data ^ (1 << bit) for bit in range(config.width)]
        for global_delay in range(self.maximum_delay+1):
            delays = [min(global_delay, capacity) for capacity in config.capacities]
            await self.configure(delays)
            for pattern in patterns:
                data = [pattern ^ (self.maximum_data if c % 2 else 0) for c in range(config.channels)]
                await self.send('data_patterns', i_advance=1, i_input_valid=self.all_channels, i_input_data=pack(data, config.width))
            for c in range(config.channels):
                await self.send('independent_channel_token', i_input_valid=1 << c, i_input_data=self.data())
            for index in range(2*self.maximum_delay+8):
                valid = self.all_channels if index % 2 else 0
                await self.send('alternating_tokens_bubbles', i_input_valid=valid,
                    i_input_data=self.data() if valid else 'z'*config.widths['i_input_data'])
            await self.drain()
            for count in range(global_delay+1):
                await self.configure(delays)
                await self.fill(count)
                # Zero-delay channels must not begin a pending bypass operand
                # during this separate delayed-storage stall experiment.
                valid = sum(1 << c for c, delay in enumerate(delays) if delay > 0)
                for _ in range(count % (STALL_LIMIT+1)):
                    await self.send('occupied_stall', i_advance=0, i_input_valid=valid)
                await self.drain()
                await self.fill(count)
                for c in range(config.channels):
                    await self.send('per_channel_flush', i_advance=0, i_input_valid=0, i_flush=1 << c)
                await self.send('flush_release', edge=False, i_flush=0)

    async def stalls_disables_and_reconfiguration(self):
        config = self.config
        await self.configure(list(config.capacities))
        for length in range(STALL_LIMIT+1):
            await self.fill(self.maximum_delay)
            valid = sum(1 << c for c, capacity in enumerate(config.capacities) if capacity)
            for _ in range(length):
                await self.send('stall_length', i_advance=0, i_input_valid=valid)
            await self.drain()
        await self.configure([0]*config.channels)
        for _ in range(32):
            await self.send('pending_bypass_stall', i_advance=0, i_input_valid=self.all_channels,
                **({'i_input_data': self.data()} if self.ports['i_input_valid'].count('1') == 0 else {}))
        await self.send('resume_bypass', i_advance=1)
        await self.send('bypass_done', i_input_valid=0)
        for enabled in range(config.channels+1):
            for transferred in range(enabled+1):
                await self.send('enable_transfer_population', i_advance=1,
                    i_channel_enable=(1 << enabled)-1, i_input_valid=(1 << transferred)-1, i_input_data=self.data())
        await self.configure(list(config.capacities))
        await self.fill(max(1, self.maximum_delay))
        await self.send('disable_preserves_live_state', i_channel_enable=0, i_advance=1,
            i_input_valid='x'*config.channels, i_input_data='z'*config.widths['i_input_data'])
        await self.send('reenable_same_owner', i_channel_enable=self.all_channels, i_input_valid=0)
        await self.drain()
        # Empty reconfiguration is effective without flush. An allocated stage
        # above a smaller selected delay must remain invalid and inactive.
        await self.send('empty_reconfigure', i_delay=0, i_advance=1, i_input_valid=0)
        await self.send('empty_reconfigure_back', i_delay=pack(config.capacities, config.delay_width))
        await self.fill(max(1, self.maximum_delay))
        await self.send('flush_clamps_before_edge', edge=False, i_flush=self.all_channels,
            i_delay=0, i_advance=0, i_input_valid=0)
        await self.send('flush_reconfiguration_edge')
        await self.send('flush_release', edge=False, i_flush=0)

    async def illegal_and_ignored(self):
        config = self.config
        for c, capacity in enumerate(config.capacities):
            for delay in range(capacity+1, 1 << config.delay_width):
                delays = list(config.capacities)
                delays[c] = 0
                await self.configure(delays)
                await self.fill(max(1, self.maximum_delay))
                delays[c] = delay
                await self.send('illegal_delay_no_alias', i_delay=pack(delays, config.delay_width),
                    i_advance=0, i_input_valid=0)
                await self.send('illegal_delay_no_update', i_advance=1, i_input_valid=self.all_channels, i_input_data=self.data())
                await self.configure([0]*config.channels)
        for state in 'xz':
            await self.configure([0]*config.channels)
            await self.send('disabled_unknown_pins', i_channel_enable=0,
                i_delay=state*config.widths['i_delay'], i_input_valid=state*config.channels,
                i_input_data=state*config.widths['i_input_data'], i_advance=1)
            await self.configure(list(config.capacities))
            for _ in range(max(1, self.maximum_delay)):
                await self.send('invalid_unknown_data', i_advance=1, i_input_valid=0,
                    i_input_data=state*config.widths['i_input_data'])
            # Input-valid is unconsumed for enabled delayed channels in a stall.
            valid = ''.join(state if capacity else '0' for capacity in reversed(config.capacities))
            await self.send('stalled_unknown_inputs', i_advance=0, i_input_valid=valid,
                i_input_data=state*config.widths['i_input_data'])
            await self.configure([0]*config.channels)

    async def resets_and_priority(self):
        config = self.config
        for count in range(self.maximum_delay+1):
            await self.configure(list(config.capacities))
            await self.fill(count)
            await self.send('reset_to_new_context', i_rstb=0, i_delay=0,
                i_advance=1, i_input_valid=self.all_channels, i_flush=self.all_channels)
            await self.send('release', edge=False, i_rstb=1, i_advance=0, i_input_valid=0, i_flush=0)
        for rstb, flush, advance in product((0, 1), repeat=3):
            await self.configure(list(config.capacities))
            await self.fill(max(1, self.maximum_delay))
            await self.send('reset_flush_advance_cross', i_rstb=rstb, i_flush=self.all_channels*flush,
                i_advance=advance, i_input_valid=0, i_input_data=self.data())
            await self.reset()
        for _ in range(2):
            await self.configure(list(config.capacities))
            await self.fill(max(1, self.maximum_delay))
            await self.send('between_edge_reset', edge=False, i_rstb=0, i_advance=0, i_input_valid=0)
            await self.send('unclocked_reset_release', edge=False, i_rstb=1)
            await self.drain()
        await self.reset()

    async def randomized(self):
        config, rng = self.config, self.rng
        pending = {}
        for index in range(config.random_cycles):
            rstb, advance = int(rng.randrange(97) != 0), int(rng.randrange(4) != 0)
            flush = rng.getrandbits(config.channels) if rng.randrange(5) == 0 else 0
            enabled = rng.getrandbits(config.channels)
            delays, data, valid = self.delays(), [], []
            empty = self.last.ports['o_channel_empty']
            for c, capacity in enumerate(config.capacities):
                cancelled = not rstb or (flush >> c) & 1
                if c in pending and not cancelled:
                    enabled |= 1 << c
                    delays[c] = 0
                    data.append(pending[c])
                    valid.append('1')
                    continue
                if cancelled or empty[-c-1] == '1':
                    if rng.randrange(3) == 0:
                        delays[c] = rng.randrange(1 << config.delay_width)
                    else:
                        delays[c] = rng.randrange(capacity+1)
                token_valid = rng.randrange(2)
                word = bits(rng.getrandbits(config.width), config.width)
                if not token_valid and rng.randrange(3) == 0:
                    word = rng.choice('xz')*config.width
                data.append(word)
                valid.append(str(token_valid))
            item = await self.send(f'random:{index}', random=True, i_rstb=rstb, i_advance=advance,
                i_flush=flush, i_channel_enable=enabled, i_delay=pack(delays, config.delay_width),
                i_input_valid=pack(valid, 1), i_input_data=pack(data, config.width))
            pending = {c: data[c] for c in range(config.channels) if rstb and not (flush >> c) & 1
                and (enabled >> c) & 1 and delays[c] == 0 and valid[c] == '1' and not advance}
        data = [pending.get(c, '0'*config.width) for c in range(config.channels)]
        await self.send('finish_pending_bypass', i_rstb=1, i_advance=1, i_flush=0,
            i_input_valid=sum(1 << c for c in pending), i_input_data=pack(data, config.width))
        await self.drain()

    async def probe(self):
        config = self.config
        field, state, bit = config.probe.split(':')
        if field.startswith('bypass_'):
            await self.configure([0]*config.channels)
            await self.send('probe_pending_bypass', i_advance=0, i_input_valid=self.all_channels, i_input_data=self.data())
            if field == 'bypass_data':
                await self.send('unstable_bypass_data', i_input_data=int(self.ports['i_input_data'], 2) ^ 1)
            else:
                await self.send('unstable_bypass_valid', i_input_valid=0)
        else:
            await self.configure(list(config.capacities))
            await self.fill(max(1, self.maximum_delay))
            if field == 'delay_boundary':
                await self.send('illegal_live_reconfiguration', i_delay=0, i_advance=int(state),
                    i_channel_enable=0 if bit == 'disabled' else self.all_channels, i_input_valid=0)
            elif field == 'unclocked_flush_boundary':
                await self.send('flush_without_edge', edge=False, i_flush=self.all_channels, i_delay=0, i_advance=0, i_input_valid=0)
                await self.send('flush_never_committed', edge=False, i_flush=0)
            else:
                word = list(self.ports[field])
                word[len(word)-1-int(bit)] = state
                await self.send('unknown_consumed_input', **{field: ''.join(word)})
        assert False, 'Illegal stimulus did not trigger its live assertion'

    async def body(self):
        await self.reset()
        if self.config.probe:
            await self.probe()
            return
        await self.all_delays()
        await self.stalls_disables_and_reconfiguration()
        await self.illegal_and_ignored()
        await self.resets_and_priority()
        await self.randomized()
