"""Directed timing boundaries, adverse physical handshakes and random policies."""

import random
from pyuvm import uvm_sequence
from tile_power_controller.model import number
from tile_power_controller.transaction import INPUTS, PowerItem, STATES as P


class PowerSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('tile_power_sequence')
        self.c = c
        self.rng = random.Random(c.seed)
        self.cycle = 0
        self.last = None

    async def tick(self, label='idle', *, edge=True, random=False, **ports):
        item = PowerItem(f'{self.cycle}:{label}', ports, edge=edge, random=random)
        item.reset_from = (
            self.output('o_power_state') if self.last and ports.get('i_aon_rstb', 1) != 1 else None
        )
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item
        self.cycle += 1
        return item

    def output(self, n):
        return number(self.last.post.ports[n])

    async def wait(self, count, label='wait', **ports):
        for _ in range(count):
            await self.tick(label, **ports)

    async def until(self, state, **ports):
        limit = (
            30
            + self.c.POWER_GOOD_SYNC_STAGES
            + self.c.POWER_STABLE_CYCLES
            + self.c.RESET_HOLD_CYCLES
            + self.c.WAKEUP_STABILIZE_CYCLES
            + self.c.ISOLATION_SETUP_CYCLES
        )
        for _ in range(limit):
            if self.output('o_power_state') == P[state]:
                return
            await self.tick('until-' + state, **ports)
        raise AssertionError(f'State {state} not reached, now {self.output("o_power_state")}')

    async def configure(self, **overrides):
        ports = (
            dict(
                i_config_valid=1,
                i_config_auto_idle_enable=0,
                i_config_wake_enable=(1 << self.c.NUM_WAKE_SOURCES) - 1,
                i_config_context_check=1,
                i_config_context_id=0,
            )
            | overrides
        )
        for _ in range(10):
            item = await self.tick('configure', **ports)
            if number(item.post.ports['o_config_accepted']) == 1:
                return
        raise AssertionError('Policy not accepted')

    async def boot(self):
        await self.tick('reset', i_aon_rstb=0)
        await self.tick('reset-held', i_aon_rstb=0, edge=False)
        await self.tick('release')
        await self.until('ACTIVE')
        assert self.output('o_tile_accept_enable') == 0
        await self.configure()
        await self.wait(2)

    async def issue(self, cmd, **ports):
        item = await self.tick('command', i_command_valid=1, i_command=cmd, **ports)
        assert number(item.pre.ports['o_command_ready']) == 1
        return item

    async def command(self, cmd, state, **ports):
        await self.issue(cmd, **ports)
        await self.until(state, **ports)

    async def run(self):
        await self.command(0, 'ACTIVE')
        await self.wait(3)

    async def error_clear(self):
        await self.tick('clear-error', i_error_clear=1)

    async def timeout_phase(self, phase):
        c = self.c
        await self.boot()
        if phase == 'drain':
            await self.issue(1, i_tile_quiescent=0, i_drain_done=0)
            limits, controls = c.DRAIN_TIMEOUT_CYCLES, dict(i_tile_quiescent=0, i_drain_done=0)
        elif phase == 'save':
            await self.issue(2, i_retention_save_ack=0)
            await self.until('SAVING', i_retention_save_ack=0)
            limits, controls = c.ACK_TIMEOUT_CYCLES, dict(i_retention_save_ack=0)
        elif phase == 'restore':
            await self.command(2, 'RETENTION')
            await self.issue(0, i_retention_restore_ack=0)
            await self.until('RESTORING', i_retention_restore_ack=0)
            limits, controls = c.ACK_TIMEOUT_CYCLES, dict(i_retention_restore_ack=0)
        elif phase == 'power_down':
            await self.issue(3, i_power_good_async=1)
            await self.until('POWERING_DOWN', i_power_good_async=1)
            limits, controls = c.POWER_TIMEOUT_CYCLES, dict(i_power_good_async=1)
        else:
            if c.SUPPORT_POWER_GATING:
                await self.command(3, 'OFF')
                await self.issue(0, i_power_good_async=0)
            else:
                await self.tick('reset', i_aon_rstb=0, i_power_good_async=0)
                # Start counting only once synchronized controller reset releases.
                await self.tick('release', edge=False, i_power_good_async=0)
                if c.ASYNC_RESET:
                    await self.wait(2, 'reset-release', i_power_good_async=0)
            limits, controls = c.POWER_TIMEOUT_CYCLES, dict(i_power_good_async=0)
        await self.wait(limits - 1, 'one-before-timeout', **controls)
        assert self.output('o_fatal_error') == 0
        await self.tick('timeout-boundary', **controls)
        assert self.output('o_power_state') == P['ERROR']
        assert self.output('o_event_timeout') == self.output('o_fatal_error') == 1
        held = self.output('o_power_switch_enable')
        await self.wait(2, 'fatal-error-clear', i_error_clear=1, **controls)
        assert self.output('o_fatal_error') == 1 and self.output('o_power_switch_enable') == held

    async def reach(self, name):
        c = self.c
        if name == 'RESET':
            await self.tick('reach-reset', i_aon_rstb=0)
        elif name in ('REINITIALIZING', 'WAKEUP'):
            await self.tick('reach-reset', i_aon_rstb=0)
            await self.tick('release')
            await self.until(name)
        elif name == 'STALLED':
            await self.tick('reach-stalled', i_tile_busy=1, i_stall_reason=1)
        elif name == 'ERROR':
            await self.wait(c.POWER_GOOD_SYNC_STAGES + 2, 'reach-error', i_power_good_async=0)
        elif name == 'DRAINING':
            await self.issue(1, i_drain_done=0, i_tile_quiescent=0)
        elif name in ('SAVING', 'ISOLATING', 'POWERING_DOWN', 'RETENTION', 'OFF'):
            cmd = 2 if name in ('SAVING', 'RETENTION') else 3
            if not c.SUPPORT_POWER_GATING:
                raise AssertionError('Unreachable advanced state')
            await self.issue(cmd)
            await self.until(name)
        elif name in ('POWERING_UP', 'RESTORING'):
            await self.command(
                2 if name == 'RESTORING' else 3, 'RETENTION' if name == 'RESTORING' else 'OFF'
            )
            await self.issue(0)
            await self.until(name)
        elif name == 'IDLE':
            await self.command(1, 'IDLE')
        assert self.output('o_power_state') == P[name]

    async def power_boundaries(self):
        c = self.c
        if not c.SUPPORT_POWER_GATING:
            return
        await self.boot()
        await self.command(3, 'OFF')
        await self.issue(0, i_power_good_async=0)
        # A pulse shorter than the qualification window cannot enable tile clocks.
        if c.POWER_STABLE_CYCLES > 1:
            await self.wait(c.POWER_STABLE_CYCLES - 1, 'short-power-pulse', i_power_good_async=1)
        else:
            await self.tick('subcycle-power-pulse', edge=False, i_power_good_async=1)
        await self.wait(c.POWER_GOOD_SYNC_STAGES + 2, 'reject-power-glitch', i_power_good_async=0)
        assert self.output('o_power_state') == P['POWERING_UP']
        assert self.output('o_tile_clock_enable') == self.output('o_power_good_sync') == 0
        await self.until('ACTIVE')
        await self.command(3, 'OFF')
        await self.issue(0, i_power_good_async=0)
        wait = c.POWER_TIMEOUT_CYCLES - c.POWER_GOOD_SYNC_STAGES - c.POWER_STABLE_CYCLES
        await self.wait(wait, 'late-power-up', i_power_good_async=0)
        await self.wait(
            c.POWER_GOOD_SYNC_STAGES + c.POWER_STABLE_CYCLES,
            'last-legal-power-up',
            i_power_good_async=1,
        )
        assert self.output('o_power_state') == P['REINITIALIZING']
        assert not self.output('o_fatal_error')
        await self.until('ACTIVE')
        await self.issue(3, i_power_good_async=1)
        await self.until('POWERING_DOWN', i_power_good_async=1)
        await self.wait(
            c.POWER_TIMEOUT_CYCLES - c.POWER_GOOD_SYNC_STAGES - 1,
            'late-power-down',
            i_power_good_async=1,
        )
        await self.wait(c.POWER_GOOD_SYNC_STAGES + 1, 'last-legal-power-down', i_power_good_async=0)
        assert self.output('o_power_state') == P['OFF'] and not self.output('o_fatal_error')
        await self.run()

    async def body(self):
        c = self.c
        await self.boot()
        # Configuration takes precedence over a command presented on the same edge.
        await self.configure(i_command_valid=1, i_command=3)
        assert self.output('o_command_accepted') == self.output('o_command_rejected') == 0
        for n in (
            'i_config_auto_idle_enable',
            'i_config_wake_enable',
            'i_config_context_check',
            'i_config_context_id',
        ):
            for x in ('x', 'z'):
                await self.tick('bad-policy', i_config_valid=1, **{n: x * c.widths[n]})
                assert self.output('o_config_rejected') == 1
                await self.error_clear()
        for reason in range(c.NUM_STALL_REASONS):
            for group in range(c.NUM_CLOCK_GROUPS):
                await self.tick(
                    'stall-groups',
                    i_tile_busy=1,
                    i_stall_reason=1 << reason,
                    i_clock_group_request=1 << group,
                )
                assert self.output('o_power_state') == P['STALLED']
                assert self.output('o_tile_clock_enable') == 1
            await self.tick(
                'active', i_tile_busy=1, i_clock_group_request=(1 << c.NUM_CLOCK_GROUPS) - 1
            )
        await self.tick('quiesce')
        await self.configure(i_config_auto_idle_enable=1)
        for count in range(1, c.IDLE_ENTRY_CYCLES):
            await self.tick('qualify-idle')
            assert self.output('o_idle_count') == count
            assert self.output('o_power_state') == P['ACTIVE']
        await self.tick('exact-idle')
        assert self.output('o_power_state') == P['IDLE']
        assert self.output('o_idle_count') == c.IDLE_ENTRY_CYCLES
        for _ in range(c.MIN_IDLE_RESIDENCY_CYCLES - 1):
            await self.tick('minimum-idle', i_tile_busy=1)
            assert self.output('o_power_state') == P['IDLE']
        await self.tick('residency-expired', i_tile_busy=1)
        assert self.output('o_power_state') == P['WAKEUP']
        await self.until('ACTIVE', i_tile_busy=1)
        await self.configure()
        # Interrupted qualification cannot carry old idle credit across work.
        await self.configure(i_config_auto_idle_enable=1)
        if c.IDLE_ENTRY_CYCLES > 1:
            await self.wait(c.IDLE_ENTRY_CYCLES - 1, 'interrupted-idle')
            await self.tick('interrupt', i_tile_busy=1)
            assert self.output('o_idle_count') == 0
        await self.configure()
        # Each wake source is exercised while clock gated, then disabled.
        for source in range(c.NUM_WAKE_SOURCES):
            await self.configure(i_config_wake_enable=0)
            await self.command(1, 'IDLE')
            await self.tick('disabled-wake', i_wakeup_event=1 << source)
            assert self.output('o_power_state') == P['IDLE']
            await self.run()
            await self.configure(i_config_wake_enable=1 << source)
            await self.command(1, 'IDLE')
            await self.tick('enabled-wake', i_wakeup_event=1 << source)
            if c.WAKE_ON_EVENT:
                assert self.output('o_power_state') == P['WAKEUP']
                await self.until('ACTIVE')
                await self.wait(3)
            else:
                assert self.output('o_power_state') == P['IDLE']
                await self.run()
        # A new mask disables wake action without erasing previously latched status.
        await self.configure()
        await self.configure(i_config_wake_enable=0, i_wakeup_event=1)
        assert self.output('o_wakeup_pending') & 1
        await self.wait(2, 'masked-pending')
        await self.run()
        await self.configure()
        await self.wait(3)
        # Illegal commands, contexts, acknowledgements and test transitions.
        for cmd in (4, 7, 'xxx', 'zzz'):
            await self.issue(cmd)
            assert self.output('o_command_rejected') == 1
            await self.error_clear()
        await self.issue(0, i_command_context_id=1)
        assert self.output('o_command_rejected') == 1
        await self.error_clear()
        for cmd, supported in ((2, c.SUPPORT_RETENTION), (3, c.SUPPORT_POWER_GATING)):
            if not supported:
                await self.issue(cmd)
                assert self.output('o_command_rejected') == 1
                await self.error_clear()
        await self.tick('wrong-save-ack', i_retention_save_ack=1)
        await self.error_clear()
        await self.tick('wrong-restore-ack', i_retention_restore_ack=1)
        await self.error_clear()
        await self.command(1, 'IDLE')
        await self.tick('illegal-test', i_test_mode=1, i_test_clock_enable=1)
        assert self.output('o_tile_clock_enable') == 0
        await self.run()
        await self.error_clear()
        for clock in (1, 0, 1):
            await self.tick('authorized-test', i_test_mode=1, i_test_clock_enable=clock)
            assert self.output('o_tile_clock_enable') == clock
            assert self.output('o_tile_accept_enable') == 0
        for name in (
            'i_test_mode',
            'i_test_clock_enable',
            'i_clock_group_request',
            'i_wakeup_event',
        ):
            for x in ('x', 'z'):
                controls = dict(i_test_mode=1, i_test_clock_enable=1)
                controls[name] = x * c.widths[name]
                await self.tick('unknown-during-test', **controls)
                assert (
                    self.output('o_tile_clock_enable') == self.output('o_clock_group_enable') == 0
                )
                await self.tick('restore-test-controls', i_test_mode=1, i_test_clock_enable=1)
                assert self.output('o_tile_clock_enable') == 1
        await self.tick('leave-test')
        # Explicit entry/wake and queued wake through irreversible shutdown.
        for cmd, target in ((1, 'IDLE'), (2, 'RETENTION'), (3, 'OFF')):
            if cmd == 2 and not c.SUPPORT_RETENTION or cmd == 3 and not c.SUPPORT_POWER_GATING:
                continue
            await self.command(cmd, target)
            await self.command(cmd, target)
            await self.run()
            if cmd > 1:
                await self.issue(cmd)
                await self.tick('wake-during-drain', i_wakeup_event=1)
                await self.until(target)
                if c.WAKE_ON_EVENT:
                    await self.until('ACTIVE')
                    await self.wait(3)
                else:
                    await self.run()
        # The command legality table is independent of enum ordering.
        stable_states = ['ACTIVE', 'STALLED', 'IDLE']
        if c.SUPPORT_POWER_GATING:
            stable_states += ['OFF']
        if c.SUPPORT_RETENTION:
            stable_states += ['RETENTION']
        targets = {0: 'ACTIVE', 1: 'IDLE', 2: 'RETENTION', 3: 'OFF'}
        for state in stable_states:
            for cmd in range(8):
                await self.boot()
                await self.reach(state)
                await self.issue(cmd)
                implemented = (
                    cmd in targets
                    and (cmd != 2 or c.SUPPORT_RETENTION)
                    and (cmd != 3 or c.SUPPORT_POWER_GATING)
                )
                legal = implemented and (
                    cmd == 0 or state in ('ACTIVE', 'STALLED', 'IDLE') or targets[cmd] == state
                )
                assert self.output('o_command_accepted') == int(bool(legal))
                assert self.output('o_command_rejected') == int(not legal)
        await self.boot()
        # All enabled sources also exercise each available main-supply-off state.
        for cmd, state in ((2, 'RETENTION'), (3, 'OFF')):
            if cmd == 2 and not c.SUPPORT_RETENTION or cmd == 3 and not c.SUPPORT_POWER_GATING:
                continue
            for source in range(c.NUM_WAKE_SOURCES):
                await self.configure(i_config_wake_enable=1 << source)
                await self.command(cmd, state)
                await self.tick('wake-source-' + state, i_wakeup_event=1 << source)
                if c.WAKE_ON_EVENT:
                    assert self.output('o_power_state') == P['POWERING_UP']
                    await self.until('ACTIVE')
                    await self.wait(3)
                else:
                    assert self.output('o_power_state') == P[state]
                    await self.run()
        # Successful drain/retention acknowledgement on the final legal edge.
        await self.issue(1, i_drain_done=0, i_tile_quiescent=0)
        await self.wait(
            c.DRAIN_TIMEOUT_CYCLES - 1, 'late-drain', i_drain_done=0, i_tile_quiescent=0
        )
        await self.tick('last-legal-drain')
        assert self.output('o_power_state') == P['IDLE'] and not self.output('o_fatal_error')
        await self.run()
        if c.SUPPORT_RETENTION:
            for phase in ('save', 'restore'):
                if phase == 'save':
                    await self.issue(2, i_retention_save_ack=0)
                    await self.until('SAVING', i_retention_save_ack=0)
                    port = 'i_retention_save_ack'
                else:
                    await self.issue(0, i_retention_restore_ack=0)
                    await self.until('RESTORING', i_retention_restore_ack=0)
                    port = 'i_retention_restore_ack'
                await self.wait(c.ACK_TIMEOUT_CYCLES - 1, 'late-ack', **{port: 0})
                await self.tick('last-legal-ack', **{port: 1})
                assert not self.output('o_fatal_error')
                await self.until('RETENTION' if phase == 'save' else 'ACTIVE')
            await self.wait(3)
        await self.power_boundaries()
        # Every reachable phase must converge through the controller reset.
        states = [
            'RESET',
            'ACTIVE',
            'STALLED',
            'IDLE',
            'DRAINING',
            'REINITIALIZING',
            'WAKEUP',
            'ERROR',
        ]
        if c.SUPPORT_POWER_GATING:
            states += ['ISOLATING', 'POWERING_DOWN', 'OFF', 'POWERING_UP']
        if c.SUPPORT_RETENTION:
            states += ['SAVING', 'RETENTION', 'RESTORING']
        for state in states:
            await self.boot()
            await self.reach(state)
            await self.tick('reset-from-' + state, i_aon_rstb=0)
            assert self.output('o_power_state') == P['RESET']
        # Loss during every powered sequencing phase contains on the AON edge.
        loss_states = ['ACTIVE', 'STALLED', 'IDLE', 'DRAINING', 'REINITIALIZING', 'WAKEUP']
        if c.SUPPORT_POWER_GATING:
            loss_states += ['ISOLATING']
        if c.SUPPORT_RETENTION:
            loss_states += ['SAVING', 'RESTORING']
        for state in loss_states:
            await self.boot()
            await self.reach(state)
            controls = dict(i_power_good_async=0)
            if state == 'DRAINING':
                controls |= dict(i_drain_done=0, i_tile_quiescent=0)
            if state == 'SAVING':
                controls['i_retention_save_ack'] = 0
            if state == 'RESTORING':
                controls['i_retention_restore_ack'] = 0
            await self.wait(c.POWER_GOOD_SYNC_STAGES + 2, 'loss-from-' + state, **controls)
            if state == 'ISOLATING' and self.output('o_power_state') in (
                P['POWERING_DOWN'],
                P['OFF'],
            ):
                # A short isolation window can legitimately finish before the synchronized loss arrives.
                assert self.output('o_isolation_enable') == 1
                assert self.output('o_tile_clock_enable') == 0
            else:
                assert self.output('o_fatal_error') == 1
        # Timeouts retain switch direction and require reset for recovery.
        phases = (
            ['drain', 'power_up']
            + (['power_down'] if c.SUPPORT_POWER_GATING else [])
            + (['save', 'restore'] if c.SUPPORT_RETENTION else [])
        )
        for phase in phases:
            await self.timeout_phase(phase)
        await self.boot()
        # A synchronized unknown or deassertion in a powered state is fatal.
        for level in (0, 'x', 'z'):
            await self.wait(c.POWER_GOOD_SYNC_STAGES + 2, 'power-loss', i_power_good_async=level)
            assert self.output('o_fatal_error') == 1
            await self.boot()
        # Unknown inputs cannot authorize a physical action or configuration.
        for n in INPUTS:
            if n in ('i_aon_rstb', 'i_power_good_async'):
                continue
            for x in ('x', 'z'):
                controls = {n: x * c.widths[n]}
                if n.startswith('i_config_') and n != 'i_config_valid':
                    controls['i_config_valid'] = 1
                if n in ('i_command', 'i_command_context_id'):
                    controls['i_command_valid'] = 1
                await self.tick('unknown-' + n, **controls)
                await self.error_clear()
        for x in ('x', 'z'):
            await self.tick('unknown-reset', i_aon_rstb=x)
            assert self.output('o_tile_accept_enable') == self.output('o_tile_clock_enable') == 0
            await self.boot()
        await self.tick(
            'held-clock',
            edge=False,
            i_tile_busy=1,
            i_clock_group_request=(1 << c.NUM_CLOCK_GROUPS) - 1,
        )
        # Randomized concurrent controls; the peer independently follows actual
        # power and retention requests. Inject bounded faults and periodic reset.
        for cycle in range(c.random_cycles):
            if cycle and cycle % 200 == 0:
                await self.boot()
            ports = dict(
                i_tile_busy=self.rng.randrange(2),
                i_tile_quiescent=self.rng.randrange(2),
                i_stall_reason=self.rng.getrandbits(c.NUM_STALL_REASONS),
                i_clock_group_request=self.rng.getrandbits(c.NUM_CLOCK_GROUPS),
                i_wakeup_event=self.rng.getrandbits(c.NUM_WAKE_SOURCES)
                if self.rng.random() < 0.05
                else 0,
                i_command_valid=int(self.rng.random() < 0.08),
                i_command=self.rng.randrange(5),
                i_config_valid=int(self.rng.random() < 0.03),
                i_config_auto_idle_enable=self.rng.randrange(2),
                i_config_wake_enable=self.rng.getrandbits(c.NUM_WAKE_SOURCES),
                i_config_context_check=1,
                i_config_context_id=0,
                i_error_clear=int(self.rng.random() < 0.1),
            )
            await self.tick('random', random=True, **ports)
        await self.boot()
