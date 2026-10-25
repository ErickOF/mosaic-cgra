"""Cycle-accurate reference using explicit transition and control tables.

Timers have independent phase ownership. The model reads only public stimulus;
internal counter observations are checked separately by the scoreboard.
"""

from mosaic_uvm.logic import bits
from tile_power_controller.config import TIMERS
from tile_power_controller.transaction import STATES as P, ERRORS as E, STABLE, OUTPUTS


def number(value):
    return int(value, 2) if set(value) <= {'0', '1'} else None


class PowerModel:
    def __init__(self, c):
        self.c = c
        self.release = [0, 0]
        self.reset()

    def reset(self):
        self.state, self.target, self.previous = P['RESET'], P['ACTIVE'], P['RESET']
        self.policy = dict(valid=0, auto=0, mask=0, check=0, context=0)
        self.pending = self.command_pending = self.authorized = self.test = self.error = (
            self.fatal
        ) = 0
        self.timers = dict.fromkeys(TIMERS, 0)
        self.residency = 0
        self.pipeline = [0] * self.c.POWER_GOOD_SYNC_STAGES
        self.tile_release = [0, 0]
        self.control = dict(
            accept=0,
            drain=0,
            clock=0,
            groups=0,
            operand=1,
            write=1,
            isolation=1,
            save=0,
            restore=0,
            power=1,
            hold=1,
            good=0,
        )
        self.events = dict.fromkeys(
            (
                'o_config_accepted',
                'o_config_rejected',
                'o_command_accepted',
                'o_command_rejected',
                'o_command_done',
                'o_event_state_change',
                'o_event_idle_entry',
                'o_event_wakeup',
                'o_event_stall_entry',
                'o_event_retention_entry',
                'o_event_off_entry',
                'o_event_timeout',
            ),
            0,
        )

    def effective_reset(self, p):
        return p['i_aon_rstb'] == 1 and (not self.c.ASYNC_RESET or self.release[-1] == 1)

    def settle(self, ports):
        p = {n: number(v) for n, v in ports.items()}
        if p['i_aon_rstb'] != 1:
            self.release = [0, 0]
        if self.c.ASYNC_RESET and not self.effective_reset(p):
            self.reset()
        if not self.effective_reset(p) or self.control['hold']:
            self.tile_release = [0, 0]

    def plan(self, ports):
        c, state = self.c, self.state
        p = {n: number(v) for n, v in ports.items()}
        run = self.effective_reset(p)
        stable = state in STABLE
        functional = state in (P['ACTIVE'], P['STALLED'])
        globals_ = (
            'i_error_clear',
            'i_test_mode',
            'i_test_clock_enable',
            'i_config_valid',
            'i_command_valid',
            'i_tile_busy',
            'i_tile_quiescent',
            'i_drain_done',
            'i_stall_reason',
            'i_clock_group_request',
            'i_wakeup_event',
            'i_retention_save_ack',
            'i_retention_restore_ack',
        )
        known = all(p[n] is not None for n in globals_)
        policy_known = all(
            p[n] is not None
            for n in (
                'i_config_auto_idle_enable',
                'i_config_wake_enable',
                'i_config_context_check',
                'i_config_context_id',
            )
        )
        captured = sum(
            1 << b
            for b, v in enumerate(reversed(ports['i_wakeup_event']))
            if v == '1' and self.policy['mask'] >> b & 1
        )
        waking = bool(c.WAKE_ON_EVENT and self.pending & self.policy['mask'])
        requested_wake = bool(c.WAKE_ON_EVENT and (self.pending | captured) & self.policy['mask'])
        synchronized = self.pipeline[-1]
        power_ready = (
            synchronized == 1 and self.timers['qualification'] >= c.POWER_STABLE_CYCLES - 1
        )
        base = (
            run
            and power_ready
            and state in (P['ACTIVE'], P['IDLE'])
            and not self.command_pending
            and not waking
            and p['i_tile_quiescent'] == 1
            and p['i_test_mode'] == 0
            and not self.fatal
            and known
        )
        config_accept = base and p['i_config_valid'] == 1
        config_good = config_accept and policy_known
        ready = (
            run
            and stable
            and state != P['ERROR']
            and not self.command_pending
            and p['i_test_mode'] == 0
            and not self.fatal
            and not config_accept
            and known
            and (state in (P['RETENTION'], P['OFF']) or power_ready)
        )
        command_accept = ready and p['i_command_valid'] == 1
        quiescent = base and not config_accept and not command_accept
        command_target = {0: P['ACTIVE'], 1: P['IDLE'], 2: P['RETENTION'], 3: P['OFF']}.get(
            p['i_command'], self.target
        )
        command_error = 0
        if (
            p['i_command'] not in (0, 1, 2, 3)
            or p['i_command_context_id'] is None
            or p['i_command'] == 2
            and not c.SUPPORT_RETENTION
            or p['i_command'] == 3
            and not c.SUPPORT_POWER_GATING
        ):
            command_error = E['COMMAND']
        elif self.policy['check'] and p['i_command_context_id'] != self.policy['context']:
            command_error = E['CONTEXT']
        elif (
            command_target != P['ACTIVE']
            and not functional
            and state != P['IDLE']
            and state != command_target
        ):
            command_error = E['TRANSITION']
        legal = command_error == 0
        synchronized = self.pipeline[-1]
        power_ready = (
            synchronized == 1 and self.timers['qualification'] >= c.POWER_STABLE_CYCLES - 1
        )
        idle_qualify = (
            run
            and functional
            and self.policy['valid']
            and self.policy['auto']
            and p['i_tile_busy'] == 0
            and p['i_tile_quiescent'] == 1
            and p['i_stall_reason'] == 0
            and known
            and not requested_wake
            and p['i_command_valid'] == 0
            and p['i_config_valid'] == 0
            and p['i_test_mode'] == 0
            and not self.fatal
        )
        new, target, pending, authorized, test = (
            state,
            self.target,
            self.command_pending,
            self.authorized,
            self.test,
        )
        wakes = self.pending | captured
        error = (
            E['UNKNOWN']
            if not known or synchronized is None
            else E['CONFIG']
            if config_accept and not config_good
            else command_error
            if command_accept and not legal
            else E['ACK']
            if p['i_retention_save_ack'] == 1
            and not self.control['save']
            or p['i_retention_restore_ack'] == 1
            and not self.control['restore']
            else 0
        )
        fatal = timeout = wake_started = done = False
        if p['i_test_mode'] == 0:
            test = 0
        elif p['i_test_mode'] == 1 and not self.test:
            if (
                state == P['ACTIVE']
                and power_ready
                and self.authorized
                and not self.command_pending
                and known
            ):
                test = 1
            elif not error:
                error = E['TEST']
        # Phase transitions are described as destination predicates, separately
        # from the stable-state command and activity policy below.
        phase_success = {
            P['RESET']: (power_ready, P['REINITIALIZING']),
            P['DRAINING']: (
                known and p['i_tile_quiescent'] == p['i_drain_done'] == 1,
                {P['IDLE']: P['IDLE'], P['RETENTION']: P['SAVING'], P['OFF']: P['ISOLATING']}.get(
                    self.target, P['ERROR']
                ),
            ),
            P['SAVING']: (known and p['i_retention_save_ack'] == 1, P['ISOLATING']),
            P['ISOLATING']: (
                known and self.timers['isolation'] >= c.ISOLATION_SETUP_CYCLES - 1,
                P['POWERING_DOWN'],
            ),
            P['POWERING_DOWN']: (synchronized == 0, self.target),
            P['POWERING_UP']: (
                power_ready,
                P['RESTORING'] if self.previous == P['RETENTION'] else P['REINITIALIZING'],
            ),
            P['RESTORING']: (known and p['i_retention_restore_ack'] == 1, P['WAKEUP']),
            P['REINITIALIZING']: (
                known and not self.control['hold'] and self.tile_release[-1],
                P['WAKEUP'],
            ),
            P['WAKEUP']: (
                known and self.timers['wake'] >= c.WAKEUP_STABILIZE_CYCLES - 1,
                P['ACTIVE'],
            ),
        }
        deadlines = {
            P['RESET']: ('power_up', c.POWER_TIMEOUT_CYCLES, E['POWER_UP_TIMEOUT']),
            P['DRAINING']: ('drain', c.DRAIN_TIMEOUT_CYCLES, E['DRAIN_TIMEOUT']),
            P['SAVING']: ('save', c.ACK_TIMEOUT_CYCLES, E['SAVE_TIMEOUT']),
            P['RESTORING']: ('restore', c.ACK_TIMEOUT_CYCLES, E['RESTORE_TIMEOUT']),
            P['POWERING_UP']: ('power_up', c.POWER_TIMEOUT_CYCLES, E['POWER_UP_TIMEOUT']),
            P['POWERING_DOWN']: ('power_down', c.POWER_TIMEOUT_CYCLES, E['POWER_DOWN_TIMEOUT']),
        }
        if state in phase_success:
            success, destination = phase_success[state]
            if success:
                new = destination
            elif state in deadlines:
                timer, limit, diagnosis = deadlines[state]
                if self.timers[timer] >= limit - 1:
                    timeout, error = True, diagnosis
        elif (
            stable
            and state != P['ERROR']
            and known
            and not config_accept
            and not self.test
            and p['i_test_mode'] == 0
        ):
            if command_accept and legal:
                target, pending = command_target, 1
                if command_target == state or command_target == P['ACTIVE'] and functional:
                    new, done, pending = command_target, True, 0
                elif command_target == P['ACTIVE']:
                    new, wake_started = (
                        P['WAKEUP'] if state == P['IDLE'] else P['POWERING_UP'],
                        True,
                    )
                else:
                    new = P['DRAINING']
            elif not command_accept:
                if requested_wake:
                    target = P['ACTIVE']
                    if not functional:
                        new, wake_started = (
                            P['WAKEUP'] if state == P['IDLE'] else P['POWERING_UP'],
                            True,
                        )
                elif (
                    state == P['IDLE']
                    and p['i_tile_busy'] == 1
                    and self.residency >= c.MIN_IDLE_RESIDENCY_CYCLES - 1
                ):
                    target, new, wake_started = P['ACTIVE'], P['WAKEUP'], True
                elif functional:
                    if idle_qualify and self.timers['idle'] >= c.IDLE_ENTRY_CYCLES - 1:
                        new = target = P['IDLE']
                    else:
                        new = (
                            P['STALLED']
                            if p['i_tile_busy'] == 1 and p['i_stall_reason']
                            else P['ACTIVE']
                        )
        elif state not in STABLE and state not in phase_success:
            fatal, error = True, E['SEQUENCE']
        if (
            state
            not in (
                P['RESET'],
                P['POWERING_UP'],
                P['POWERING_DOWN'],
                P['RETENTION'],
                P['OFF'],
                P['ERROR'],
            )
            and not power_ready
        ):
            fatal, timeout, error = True, False, E['POWER_LOSS']
        if fatal or timeout or self.fatal:
            new, pending, test = P['ERROR'], 0, 0
            done = wake_started = False
        else:
            if pending and new in STABLE and new == target:
                done, pending = True, 0
            if done and target == P['ACTIVE']:
                authorized = 1
            if new in (P['DRAINING'], P['IDLE']):
                authorized = 0
            if wake_started or functional and requested_wake or done and target == P['ACTIVE']:
                wakes = self.pending & ~self.policy['mask'] | captured
        return dict(
            p=p,
            run=run,
            known=known,
            stable=stable,
            base=base,
            config_accept=config_accept,
            config_good=config_good,
            command_ready=ready,
            command_accept=command_accept,
            command_legal=legal,
            quiescent=quiescent,
            new=new,
            target=target,
            pending=pending,
            authorized=authorized,
            test=test,
            wakes=wakes,
            error=error,
            fatal=fatal,
            timeout=timeout,
            wake_started=wake_started,
            done=done,
            power_ready=power_ready,
            idle_qualify=idle_qualify,
        )

    def evaluate(self, ports):
        q = self.plan(ports)
        c, ctrl = self.c, self.control
        mapping = dict(
            o_tile_accept_enable='accept',
            o_drain_request='drain',
            o_tile_clock_enable='clock',
            o_clock_group_enable='groups',
            o_operand_isolation_enable='operand',
            o_write_disable='write',
            o_isolation_enable='isolation',
            o_retention_save='save',
            o_retention_restore='restore',
            o_power_switch_enable='power',
            o_power_good_sync='good',
        )
        safe = dict(
            accept=0,
            drain=0,
            clock=0,
            groups=0,
            operand=1,
            write=1,
            isolation=1,
            save=0,
            restore=0,
            power=1,
            hold=1,
            good=0,
        )
        out = {n: (ctrl[k] if q['run'] else safe[k]) for n, k in mapping.items()}
        out |= dict(
            o_config_ready=q['base'],
            o_command_ready=q['command_ready'],
            o_quiescent=q['quiescent'],
            o_power_state=self.state,
            o_target_state=self.target,
            o_previous_stable_state=self.previous,
            o_transition_active=self.state not in STABLE,
            o_idle=self.state in (P['IDLE'], P['RETENTION'], P['OFF']),
            o_policy_valid=self.policy['valid'],
            o_active_context_id=self.policy['context'],
            o_wakeup_pending=self.pending,
            o_error_code=self.error,
            o_error=bool(self.error),
            o_fatal_error=self.fatal,
            o_idle_count=self.timers['idle'],
            o_state_residency=self.residency,
            o_tile_reset_request=not self.tile_release[-1],
        )
        out |= {n: v if q['run'] else 0 for n, v in self.events.items()}
        return {n: bits(int(out[n]), c.widths[n]) for n in OUTPUTS}, q

    def step(self, ports):
        c, old = self.c, self.state
        q = self.plan(ports)
        p, new = q['p'], q['new']
        tile_release = (
            [1, self.tile_release[0]] if q['run'] and not self.control['hold'] else [0, 0]
        )
        self.release = [1, self.release[0]] if p['i_aon_rstb'] == 1 else [0, 0]
        if not q['run']:
            self.reset()
            return q
        ctrl = dict(
            accept=0,
            drain=0,
            clock=0,
            groups=0,
            operand=1,
            write=1,
            isolation=1,
            save=0,
            restore=0,
            power=self.control['power'],
            hold=1,
            good=int(q['power_ready']),
        )
        groups = sum(
            1 << b for b, v in enumerate(reversed(ports['i_clock_group_request'])) if v == '1'
        )
        wake_groups = c.WAKEUP_CLOCK_GROUP_MASK | c.CLOCK_GROUP_ALWAYS_ON_MASK
        if new == P['RESET']:
            ctrl['power'] = 1
        elif new in (P['ACTIVE'], P['STALLED']):
            accept = bool(
                (self.policy['valid'] or q['config_good'])
                and not q['test']
                and p['i_test_mode'] == 0
                and q['known']
            )
            ctrl.update(
                power=1,
                isolation=0,
                hold=0,
                clock=int(q['power_ready']),
                groups=groups | c.CLOCK_GROUP_ALWAYS_ON_MASK,
                accept=int(accept),
                operand=int(not accept or new == P['STALLED'] and p['i_clock_group_request'] == 0),
                write=int(not accept),
            )
        elif new == P['IDLE']:
            ctrl.update(power=1, isolation=0, hold=0)
        elif new in (
            P['DRAINING'],
            P['SAVING'],
            P['ISOLATING'],
            P['RESTORING'],
            P['REINITIALIZING'],
            P['WAKEUP'],
        ):
            ctrl.update(
                power=1,
                clock=int(q['power_ready']),
                groups=wake_groups,
                drain=int(new == P['DRAINING']),
                save=int(new == P['SAVING']),
                restore=int(
                    new == P['RESTORING'] or new == P['WAKEUP'] and self.previous == P['RETENTION']
                ),
                isolation=int(
                    new in (P['ISOLATING'], P['RESTORING'], P['REINITIALIZING'])
                    or new == P['WAKEUP']
                    and self.control['isolation']
                ),
                hold=int(
                    new == P['REINITIALIZING']
                    and (
                        old != new
                        or self.control['hold']
                        and self.timers['reset'] < c.RESET_HOLD_CYCLES - 1
                    )
                ),
            )
        elif new in (P['POWERING_DOWN'], P['RETENTION'], P['OFF']):
            ctrl.update(power=0, hold=int(q['target'] == P['OFF']))
        elif new == P['POWERING_UP']:
            ctrl.update(
                power=1, hold=int(self.previous != P['RETENTION'] and old != P['RETENTION'])
            )
        elif new == P['ERROR']:
            ctrl.update(
                clock=int(bool(self.control['power'] and q['power_ready'])), groups=wake_groups
            )
        if q['test']:
            ctrl.update(
                clock=int(
                    p['i_test_mode'] == 1
                    and p['i_test_clock_enable'] == 1
                    and q['power_ready']
                    and q['known']
                ),
                groups=wake_groups,
                accept=0,
                operand=1,
                write=1,
            )
        if not ctrl['clock']:
            ctrl['groups'] = 0
        if ctrl['hold']:
            tile_release = [0, 0]
        # Timer updates use only ownership and public handshake predicates.
        owners = dict(
            drain=P['DRAINING'],
            save=P['SAVING'],
            restore=P['RESTORING'],
            power_down=P['POWERING_DOWN'],
            isolation=P['ISOLATING'],
            reset=P['REINITIALIZING'],
            wake=P['WAKEUP'],
        )
        for name, param in TIMERS.items():
            limit = getattr(c, param)
            if name == 'idle':
                active = q['idle_qualify']
                self.timers[name] = min(limit, self.timers[name] + 1) if active else 0
            elif name == 'qualification':
                self.timers[name] = (
                    min(limit, self.timers[name] + 1) if self.pipeline[-1] == 1 else 0
                )
            else:
                own = (
                    old in (P['RESET'], P['POWERING_UP'])
                    if name == 'power_up'
                    else old == owners[name]
                )
                if not own or new != old:
                    self.timers[name] = 0
                elif name != 'reset' or self.control['hold']:
                    self.timers[name] = min(limit, self.timers[name] + 1)
        self.residency = (
            min((1 << 32) - 1, self.residency + 1) if old in STABLE and new == old else 0
        )
        if old in STABLE and new != old:
            self.previous = old
        if not self.error:
            self.error = q['error']
        elif q['quiescent'] and p['i_error_clear'] == 1 and not self.fatal and not q['error']:
            self.error = 0
        if q['fatal'] or q['timeout']:
            self.fatal = 1
        if q['config_good']:
            self.policy = dict(
                valid=1,
                auto=p['i_config_auto_idle_enable'],
                mask=p['i_config_wake_enable'],
                check=p['i_config_context_check'],
                context=p['i_config_context_id'],
            )
        self.events = dict(
            o_config_accepted=int(q['config_good']),
            o_config_rejected=int(q['config_accept'] and not q['config_good']),
            o_command_accepted=int(q['command_accept'] and q['command_legal']),
            o_command_rejected=int(q['command_accept'] and not q['command_legal']),
            o_command_done=int(q['done']),
            o_event_state_change=int(new != old),
            o_event_idle_entry=int(new != old and new == P['IDLE']),
            o_event_wakeup=int(q['wake_started']),
            o_event_stall_entry=int(new != old and new == P['STALLED']),
            o_event_retention_entry=int(new != old and new == P['RETENTION']),
            o_event_off_entry=int(new != old and new == P['OFF']),
            o_event_timeout=int(q['timeout']),
        )
        self.control, self.tile_release = ctrl, tile_release
        self.pipeline = [p['i_power_good_async']] + self.pipeline[:-1]
        self.state, self.target, self.command_pending = new, q['target'], q['pending']
        self.authorized, self.test, self.pending = q['authorized'], q['test'], q['wakes']
        return q
