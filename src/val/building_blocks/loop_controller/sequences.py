"""Directed specification boundaries followed by reproducible random run control."""
from random import Random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from loop_controller.transaction import INPUTS, LoopControllerItem
from loop_controller.model import packed, number


class LoopControllerSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('loop_controller_sequence')
        self.c = config
        self.rng = Random(config.seed)
        self.bus = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_iteration_ready=1,
            i_completion_ready=1, i_execution_quiescent=1)
        self.last = {}
        self.serial = 0

    async def cycle(self, label='cycle', *, edge=True, random=False, fault=None, **ports):
        self.bus.update(ports)
        item = LoopControllerItem(f'{self.serial}_{label}',
            {n: bits(v * self.c.widths[n] if isinstance(v, str) and len(v) == 1 else v,
                     self.c.widths[n]) for n, v in self.bus.items()},
            edge=edge, random=random, fault=fault)
        self.serial += 1
        await self.start_item(item)
        await self.finish_item(item)
        self.last = {n: number(v) for n, v in item.observation.ports.items()}
        return self.last

    async def wait(self, output, value=1, limit=50000, **ports):
        for _ in range(limit):
            if self.last.get(output) == value:
                return
            await self.cycle('wait_' + output, **ports)
        raise AssertionError(f'Timeout waiting for {output}={value}')

    def configuration(self, depth=None, counts=None, *, compare=None, negative=False,
                      interval=1, enable=1, initial=None, step=None):
        c = self.c
        depth = c.MAX_LOOP_DEPTH if depth is None else depth
        counts = [2] * depth if counts is None else counts
        sign = -1 if negative else 1
        steps = [sign * (k % 3 + 1) for k in range(depth)] if step is None else step
        initials = [sign * (-3 - k) for k in range(depth)] if initial is None else initial
        comps = [0] * depth if compare is None else [compare] * depth
        bounds = [0] * depth
        modes = [int(compare is not None)] * depth
        if compare is not None:
            for k in range(depth):
                post = initials[k] + counts[k] * steps[k]
                bounds[k] = post if compare in (0, 2) else post - (1 if steps[k] > 0 else -1)
        return dict(i_config_depth=depth, i_config_level_mode=packed(modes, 2),
            i_config_initial=packed(initials, c.INDEX_WIDTH),
            i_config_bound=packed(bounds, c.INDEX_WIDTH), i_config_step=packed(steps, c.INDEX_WIDTH),
            i_config_trip_count=packed(counts, c.TRIP_COUNT_WIDTH), i_config_compare=packed(comps, 3),
            i_config_initiation_interval=interval, i_config_context_id=(1 << c.CONTEXT_ID_WIDTH) - 1,
            i_config_completion_event_enable=enable, i_config_completion_event_id=c.NUM_EVENTS - 1)

    async def configure(self, fields=None, **overrides):
        fields = (self.configuration() if fields is None else fields) | overrides
        await self.cycle('config_setup', i_config_valid=0, i_start_valid=0, i_control_valid=0)
        await self.wait('o_config_ready')
        await self.cycle('config_capture', i_config_valid=1, **fields)
        self.config_result = await self.cycle('config_validate', i_config_valid=0)
        await self.cycle('config_result')

    async def start_run(self, **overrides):
        await self.cycle('start_setup', i_start_valid=0, i_config_valid=0, i_control_valid=0)
        await self.wait('o_start_ready')
        await self.cycle('start', i_start_valid=1,
            i_start_context_id=(1 << self.c.CONTEXT_ID_WIDTH) - 1,
            i_start_run_id=(self.serial & ((1 << self.c.RUN_ID_WIDTH) - 1)), **overrides)
        await self.cycle('start_release', i_start_valid=0)

    async def drain(self, random_ready=False):
        for _ in range(10000):
            if self.last.get('o_idle'):
                return
            assert not self.last.get('o_fatal_error')
            if self.last.get('o_suspended'):
                await self.command(1)
                continue
            await self.cycle('drain', i_iteration_ready=int(not random_ready or self.rng.random() < .7),
                             i_completion_ready=int(not random_ready or self.rng.random() < .6),
                             i_execution_quiescent=1, i_control_valid=0)
        raise AssertionError('Run failed to drain')

    async def command(self, command, *, owner=None, run=None):
        await self.cycle('command', i_control_valid=1, i_control_command=command,
            i_control_context_id=self.bus['i_config_context_id'] if owner is None else owner,
            i_control_run_id=self.last['o_current_run_id'] if run is None else run)
        await self.cycle('command_release', i_control_valid=0)

    async def clear(self):
        await self.cycle('clear_error', i_error_clear=1)
        await self.cycle('clear_release', i_error_clear=0)

    async def body(self):
        c = self.c
        await self.cycle('reset', i_rstb=0)
        await self.cycle('release', i_rstb=1)
        await self.start_run()  # Illegal unconfigured start is consumed.
        await self.clear()
        # Every depth, both step signs, and every carry level. Bounded modes
        # independently exercise all four comparison encodings at every level.
        for depth in range(1, c.MAX_LOOP_DEPTH + 1):
            for negative in (False, True):
                await self.configure(self.configuration(depth, negative=negative))
                await self.start_run()
                await self.drain(True)
        if c.SUPPORT_BOUNDED_MODE:
            for cmp in range(4):
                await self.configure(self.configuration(compare=cmp, negative=cmp >= 2))
                await self.start_run()
                await self.drain(True)
            # Mixed counted/bounded levels, including odd nesting depths.
            mix = self.configuration(compare=0)
            mix['i_config_level_mode'] = packed([k % 2 for k in range(c.MAX_LOOP_DEPTH)], 2)
            await self.configure(mix)
            await self.start_run()
            await self.drain(True)
        for k in range(c.MAX_LOOP_DEPTH):
            counts = [2] * c.MAX_LOOP_DEPTH
            counts[k] = 0
            await self.configure(self.configuration(counts=counts, enable=k % 2))
            await self.start_run()
            await self.drain()
        for ii in (1, 2, 3, 8, 255):
            if ii >= 1 << c.II_WIDTH:
                continue
            await self.configure(self.configuration(1, [3], interval=ii, enable=0))
            await self.start_run()
            await self.drain(True)
        # One-trip masks, bounded zero trips, and delayed completion holding.
        await self.configure(self.configuration(counts=[1] * c.MAX_LOOP_DEPTH))
        await self.start_run()
        await self.drain(True)
        if c.SUPPORT_BOUNDED_MODE:
            for cmp in range(4):
                for level in range(c.MAX_LOOP_DEPTH):
                    counts = [1] * c.MAX_LOOP_DEPTH
                    counts[level] = 0
                    await self.configure(self.configuration(counts=counts, compare=cmp, negative=cmp >= 2))
                    await self.start_run()
                    await self.drain()
        # Pause at each point in a small full Cartesian nest, with the token
        # already presented and stalled. Resume must select the next point.
        if c.SUPPORT_SUSPEND:
            await self.configure(self.configuration(counts=[2] * c.MAX_LOOP_DEPTH))
            await self.cycle('coordinate_stop_setup', i_iteration_ready=0, i_execution_quiescent=0)
            await self.start_run()
            for point in range((1 << c.MAX_LOOP_DEPTH) - 1):
                await self.wait('o_iteration_valid')
                await self.command(0)
                await self.cycle('coordinate_token_drain', i_iteration_ready=1)
                await self.cycle('coordinate_safe', i_execution_quiescent=1)
                await self.wait('o_suspended')
                await self.cycle('coordinate_resume_setup', i_iteration_ready=0)
                await self.command(1)
            await self.drain(True)
            # Pause with no token presented (nonzero pacing).
            if c.II_WIDTH > 1:
                await self.configure(self.configuration(1, [4], interval=3))
                await self.cycle('pacing_pause_setup', i_iteration_ready=1)
                await self.start_run()
                await self.command(0)
                await self.wait('o_suspended')
                await self.command(1)
                await self.drain()
        # Last/post signed-boundary arithmetic, including post outside I bits.
        for cmp, first, step in ((0, (1 << (c.INDEX_WIDTH - 1)) - 3, 1),
                                  (2, -(1 << (c.INDEX_WIDTH - 1)) + 2, -1)):
            await self.configure(self.configuration(1, [3], compare=None, initial=[first], step=[step]))
            await self.start_run()
            await self.drain()
        # Maximum trip, exact maximum total, and zero annihilation of overflow.
        max_trip = (1 << min(c.TRIP_COUNT_WIDTH, c.INDEX_WIDTH, c.LINEAR_COUNT_WIDTH)) - 1
        await self.configure(self.configuration(1, [max_trip], initial=[-(max_trip // 2)], step=[1]))
        await self.cycle('discard_large_config', i_flush=1)
        await self.cycle('flush_release', i_flush=0)
        if c.LINEAR_COUNT_WIDTH < min(c.TRIP_COUNT_WIDTH, c.INDEX_WIDTH):
            await self.configure(self.configuration(1, [(1 << c.LINEAR_COUNT_WIDTH) - 1],
                                                   initial=[0], step=[1]))
        if c.LINEAR_COUNT_WIDTH == 64 and c.MAX_LOOP_DEPTH >= 4 and min(c.INDEX_WIDTH, c.TRIP_COUNT_WIDTH) >= 24:
            await self.configure(self.configuration(counts=[65535, 641, 65537, 6700417] +
                [1] * (c.MAX_LOOP_DEPTH - 4), initial=[0] * c.MAX_LOOP_DEPTH,
                step=[1] * c.MAX_LOOP_DEPTH))
        if c.MAX_LOOP_DEPTH >= 3:
            counts = [1] * c.MAX_LOOP_DEPTH
            counts[:3] = [(1 << min(c.TRIP_COUNT_WIDTH, c.INDEX_WIDTH - 1)) - 1] * 2 + [0]
            await self.configure(self.configuration(counts=counts,
                initial=[0] * c.MAX_LOOP_DEPTH, step=[1] * c.MAX_LOOP_DEPTH))
            await self.start_run()
            await self.drain()
        await self.configure(self.configuration(1, [2]))
        # Reject candidates atomically and prove the old configuration still runs.
        bad = [dict(i_config_depth=0), dict(i_config_initiation_interval=0),
               dict(i_config_level_mode=3), dict(i_config_compare=7), dict(i_config_step=0),
               dict(i_config_initial=packed([(1 << (c.INDEX_WIDTH - 1)) - 1], c.INDEX_WIDTH)),
               dict(i_config_context_id='x'), dict(i_config_level_mode='x'),
               dict(i_config_compare='z'), dict(i_config_depth='x'),
               dict(i_config_trip_count='x'), dict(i_config_step='z'),
               dict(i_config_completion_event_enable='x')]
        if c.MAX_LOOP_DEPTH > 1:
            bad += [dict(i_config_step=1 | (1 << c.INDEX_WIDTH)),
                    dict(i_config_initial='x' + '0' * (c.MAX_LOOP_DEPTH * c.INDEX_WIDTH - 1))]
        else:
            # A dedicated larger-depth profile covers inactive field rejection.
            pass
        if c.SUPPORT_BOUNDED_MODE:
            bad += [dict(i_config_level_mode=1, i_config_bound=0)]
        else:
            bad += [dict(i_config_level_mode=1)]
        if c.NUM_EVENTS & (c.NUM_EVENTS - 1) or c.NUM_EVENTS == 1:
            bad += [dict(i_config_completion_event_id=c.NUM_EVENTS)]
        for change in bad:
            await self.configure(self.configuration(1, [2]), **change)
            await self.cycle('rejection_observed')
            await self.clear()
            await self.start_run()
            await self.drain()
        # Product overflow with representable per-level indices, including
        # single-level overflow when the linear field is narrower than a trip.
        power = c.LINEAR_COUNT_WIDTH // c.MAX_LOOP_DEPTH + 1
        if power < min(c.TRIP_COUNT_WIDTH, c.INDEX_WIDTH - 1):
            await self.configure(self.configuration(counts=[1 << power] * c.MAX_LOOP_DEPTH,
                initial=[0] * c.MAX_LOOP_DEPTH, step=[1] * c.MAX_LOOP_DEPTH))
            await self.cycle('product_error_observed')
            await self.clear()
        # Ownership rejects and unknown fields, with fail-closed state holding.
        await self.configure(self.configuration(1, [12]))
        await self.cycle('wrong_start', i_start_valid=1, i_start_context_id=0)
        await self.cycle('wrong_start_release', i_start_valid=0)
        await self.clear()
        for name in ('i_config_valid', 'i_start_valid', 'i_control_valid', 'i_iteration_ready',
                     'i_completion_ready', 'i_execution_quiescent', 'i_error_clear', 'i_flush', 'i_rstb'):
            previous = self.bus[name]
            for unknown in ('x', 'z'):
                await self.cycle('unknown_' + name, **{name: unknown})
                await self.cycle('known_' + name, **{name: previous})
            await self.clear()
        await self.cycle('unknown_start', i_start_valid=1, i_start_context_id='x')
        await self.cycle('unknown_start_release', i_start_valid=0)
        await self.clear()
        await self.cycle('stall_setup', i_iteration_ready=0, i_execution_quiescent=0)
        await self.start_run()
        await self.cycle('active_ready_unknown', i_iteration_ready='x')
        await self.cycle('active_ready_unknown_z', i_iteration_ready='z')
        await self.cycle('active_ready_known', i_iteration_ready=0)
        await self.command(3)
        await self.command('x')
        await self.command(0, run='z')
        await self.command(0, owner=0)
        if c.SUPPORT_SUSPEND:
            await self.command(0)
            await self.cycle('pending_safe_unknown', i_execution_quiescent='x')
            await self.cycle('pending_ready_unknown', i_iteration_ready='z', i_execution_quiescent=0)
            await self.cycle('pending_ready_known', i_iteration_ready=0)
            for _ in range(4):
                await self.cycle('pause_stall')
            await self.cycle('pause_token_drain', i_iteration_ready=1)
            for _ in range(4):
                await self.cycle('pause_safe_delay')
            await self.cycle('pause_safe', i_execution_quiescent=1)
            await self.wait('o_suspended')
            await self.command(1)
        if c.SUPPORT_ABORT:
            await self.command(2)
            await self.drain(True)
        else:
            await self.drain(True)
        await self.clear()
        for enable in (0, 1):
            await self.configure(self.configuration(1, [12], enable=enable))
            await self.cycle('stop_setup', i_iteration_ready=0, i_execution_quiescent=0)
            await self.start_run()
            if c.SUPPORT_SUSPEND:
                await self.command(0)
                await self.cycle('held_token', i_iteration_ready=1)
                await self.cycle('safe', i_execution_quiescent=1)
                await self.wait('o_suspended')
                if c.SUPPORT_ABORT:
                    await self.command(2)
                else:
                    await self.command(1)
            elif c.SUPPORT_ABORT:
                await self.command(2)
            await self.drain(True)
        # Deterministic random traffic, control, reset/flush and config reuse.
        await self.configure(self.configuration(1, [31]))
        for cycle in range(c.random_cycles):
            state = self.last
            fields = dict(i_config_valid=0, i_start_valid=0, i_control_valid=0, i_flush=0,
                i_rstb=1, i_iteration_ready=int(self.rng.random() < .67),
                i_completion_ready=int(self.rng.random() < .6),
                i_execution_quiescent=int(self.rng.random() < .4))
            if state.get('o_idle'):
                if not state.get('o_configured'):
                    fields.update(self.configuration(1, [31]), i_config_valid=1)
                elif self.rng.random() < .7:
                    fields.update(i_start_valid=1, i_start_context_id=self.bus['i_config_context_id'],
                                  i_start_run_id=self.rng.randrange(1 << c.RUN_ID_WIDTH))
            elif state.get('o_suspended'):
                fields.update(i_control_valid=1, i_control_command=1,
                              i_control_context_id=self.bus['i_config_context_id'],
                              i_control_run_id=state['o_current_run_id'])
            elif state.get('o_active') and self.rng.random() < .08:
                cmd = self.rng.choice([0, 2])
                fields.update(i_control_valid=1, i_control_command=cmd,
                              i_control_context_id=self.bus['i_config_context_id'],
                              i_control_run_id=state['o_current_run_id'])
            if cycle % 173 == 21:
                fields['i_flush'] = 1
            if cycle % 211 == 29:
                fields['i_rstb'] = 0
            await self.cycle('random', random=True, **fields)
        await self.cycle('random_end', i_rstb=1, i_flush=0, i_config_valid=0,
                         i_start_valid=0, i_control_valid=0)
        if self.last['o_suspended']:
            await self.command(1)
        await self.drain()
        # Reset/flush while active, safe-point pending, suspended and record held.
        for action in ('i_flush', 'i_rstb'):
            for target in ('issue', 'complete', 'record', 'pause', 'suspended', 'abort', 'validating'):
                if target in ('pause', 'suspended') and not c.SUPPORT_SUSPEND:
                    continue
                if target == 'abort' and not c.SUPPORT_ABORT:
                    continue
                await self.configure(self.configuration(1, [3]))
                await self.cycle('cut_setup', i_iteration_ready=0, i_completion_ready=0,
                                 i_execution_quiescent=0)
                if target == 'validating':
                    await self.cycle('candidate_for_cut', i_config_valid=1)
                else:
                    await self.start_run()
                    if target in ('complete', 'record'):
                        await self.cycle('finish_setup', i_iteration_ready=1)
                        await self.wait('o_completion_pending')
                        if target == 'record':
                            await self.cycle('finish_safe', i_execution_quiescent=1)
                    elif target in ('pause', 'suspended', 'abort'):
                        await self.command(2 if target == 'abort' else 0)
                        if target == 'suspended':
                            await self.cycle('drain_for_suspend', i_iteration_ready=1)
                            await self.cycle('suspend_safe', i_execution_quiescent=1)
                            await self.wait('o_suspended')
                await self.cycle('cut_' + target, **{action: int(action == 'i_flush')})
                await self.cycle('cut_release', i_flush=0, i_rstb=1, i_config_valid=0,
                    i_iteration_ready=1, i_completion_ready=1, i_execution_quiescent=1)
        # Distinguish synchronous from asynchronous reset without a clock edge.
        # On release, asynchronous state has cleared; synchronous state still
        # owns the original stalled token until the following reset clock edge.
        await self.configure(self.configuration(1, [3]))
        await self.cycle('between_edges_setup', i_iteration_ready=0)
        await self.start_run()
        await self.cycle('between_edges_assert', edge=False, i_rstb=0)
        await self.cycle('between_edges_release', edge=False, i_rstb=1)
        await self.cycle('between_edges_clocked_reset', i_rstb=0)
        await self.cycle('between_edges_reset_release', i_rstb=1)
        if c.check_internals:
            for fault in (('candidate', 'config', 'state', 'invariant') if c.PROTECT_STATE else ('invariant',)):
                await self.configure(self.configuration(1, [3]))
                if fault == 'candidate':
                    await self.cycle('fault_candidate_capture', i_config_valid=1)
                    await self.cycle('inject_candidate', i_config_valid=0, fault=fault)
                else:
                    await self.cycle('fault_setup', i_iteration_ready=0)
                    await self.start_run()
                    # Set the highest accepted-count bit, making accepted > total.
                    await self.cycle('inject_' + fault, fault=fault)
                await self.cycle('fatal_hold', i_error_clear=1)
                await self.cycle('fatal_flush', i_flush=1)
                await self.cycle('fatal_flush_release', i_flush=0)
                await self.cycle('fatal_reset', i_rstb=0)
                await self.cycle('fault_release', i_rstb=1, i_error_clear=0)
        await self.cycle('final_reset', i_rstb=0)
        await self.cycle('final_release', i_rstb=1, i_iteration_ready=1)
        await self.cycle('final_idle')
