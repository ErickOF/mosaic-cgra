"""Independent integer arithmetic and a lazy Cartesian-product reference ledger.

The reference never advances coordinates with RTL carry logic. It derives each
coordinate from the mathematical product of Python ranges (level zero fastest).
Large configurations are checked algebraically without enumerating huge nests.
"""
from math import prod
from loop_controller.transaction import OUTPUTS


def number(raw):
    if isinstance(raw, int):
        return raw
    return int(raw, 2) if set(raw.lower()) <= {'0', '1'} else None


def packed(values, width):
    return sum((value & ((1 << width) - 1)) << (k * width) for k, value in enumerate(values))


def split(value, width, depth, signed=False):
    result = [(value >> (k * width)) & ((1 << width) - 1) for k in range(depth)]
    if signed:
        result = [v - (1 << width) if v >> (width - 1) else v for v in result]
    return result


def decode(p, c):
    n = {k: number(v) for k, v in p.items() if k.startswith('i_config_') and k != 'i_config_valid'}
    if None in n.values():
        return None, 1
    n = {k.removeprefix('i_config_'): v for k, v in n.items()}
    d = n['depth']
    if not 1 <= d <= c.MAX_LOOP_DEPTH:
        return None, 2
    if n['initiation_interval'] == 0:
        return None, 6
    if n['completion_event_enable'] and n['completion_event_id'] >= c.NUM_EVENTS:
        return None, 10
    widths = dict(level_mode=2, initial=c.INDEX_WIDTH, bound=c.INDEX_WIDTH,
                  step=c.INDEX_WIDTH, trip_count=c.TRIP_COUNT_WIDTH, compare=3)
    for name, width in widths.items():
        n[name] = split(n[name], width, c.MAX_LOOP_DEPTH, name in ('initial', 'bound', 'step'))
    zero = 0 in n['trip_count'][:d]
    running_product = 1
    for level in range(c.MAX_LOOP_DEPTH):
        count, mode, compare, first, step, bound = (n[k][level] for k in
            ('trip_count', 'level_mode', 'compare', 'initial', 'step', 'bound'))
        if level >= d:
            if any(n[name][level] for name in widths):
                return None, 11
            continue
        if mode not in (0, 1) or (mode == 1 and not c.SUPPORT_BOUNDED_MODE):
            return None, 3
        if compare not in range(4):
            return None, 4
        if count and not step:
            return None, 5
        last = first + (count - 1) * step
        if count and not -(1 << (c.INDEX_WIDTH - 1)) <= last < (1 << (c.INDEX_WIDTH - 1)):
            return None, 8
        if mode == 1:
            def predicate(index):
                return (index < bound, index <= bound, index > bound, index >= bound)[compare]
            if count == 0:
                if predicate(first):
                    return None, 7
            elif (not predicate(first) or not predicate(last) or predicate(first + count * step)
                  or (compare < 2 and step < 0) or (compare >= 2 and step > 0)):
                return None, 7
        if not zero:
            running_product *= count
            if running_product >= (1 << c.LINEAR_COUNT_WIDTH):
                return None, 9
    n['total'] = prod(n['trip_count'][:d])
    return n, 0


def cartesian(counts):
    """Enumerate outer-to-inner coordinates without materializing range pools."""
    if 0 in counts:
        return
    if not counts:
        yield ()
        return
    for outer in range(counts[-1]):
        for inner in cartesian(counts[:-1]):
            yield (outer, *inner)


class LoopModel:
    def __init__(self, c):
        self.c = c
        self.reset()

    def reset(self):
        self.config = None
        self.candidate = None
        self.state = 'idle'
        self.epoch = self.run_id = self.accepted = self.pacing = 0
        self.presented = False
        self.fatal = self.fault = self.error = 0
        self.completion = 0
        self.events = {}
        self.points = iter(())
        self.point = None

    def coordinate(self):
        c, n = self.c, self.config
        ordinal = list(reversed(self.point)) + [0] * (c.MAX_LOOP_DEPTH - n['depth'])
        index = [n['initial'][k] + ordinal[k] * n['step'][k] if k < n['depth'] else 0
                 for k in range(c.MAX_LOOP_DEPTH)]
        active = (1 << n['depth']) - 1
        return dict(index=packed(index, c.INDEX_WIDTH), ordinal=packed(ordinal, c.TRIP_COUNT_WIDTH),
            first_mask=sum(1 << k for k in range(n['depth']) if ordinal[k] == 0),
            last_mask=sum(1 << k for k in range(n['depth']) if ordinal[k] == n['trip_count'][k] - 1),
            active_mask=active, linear=self.accepted, context_id=n['context_id'],
            run_id=self.run_id, epoch=self.epoch)

    def outputs(self, p):
        v = {k: number(value) for k, value in p.items()}
        enabled = v['i_rstb'] == 1
        safe = enabled and v['i_flush'] == 0 and not self.fatal and not self.fault
        idle = self.state == 'idle' and self.candidate is None
        o = dict.fromkeys(OUTPUTS, 0)
        o.update(o_start_ready=int(safe and idle),
            o_control_ready=int(safe and self.candidate is None and self.state != 'record' and (v['i_start_valid'] == 0 or not idle)),
            o_config_ready=int(safe and idle and v['i_start_valid'] == 0 and v['i_control_valid'] == 0),
            o_config_validating=int(safe and self.candidate is not None),
            o_configured=int(safe and self.config is not None),
            o_active=int(safe and self.state in ('issue', 'pause', 'abort', 'complete')),
            o_pause_pending=int(safe and self.state == 'pause'),
            o_abort_pending=int(safe and self.state == 'abort'),
            o_completion_pending=int(safe and self.state == 'complete'),
            o_suspended=int(safe and self.state == 'suspended'),
            o_current_run_id=self.run_id if safe and self.state != 'idle' else 0,
            o_current_epoch=self.epoch if enabled and not self.fault else 0,
            o_pacing_count=self.pacing if safe and self.state != 'idle' else 0,
            o_idle=int(safe and idle), o_error=int(enabled and self.error != 0),
            o_fatal_error=int(enabled and self.fatal != 0), o_error_code=self.error if enabled else 0)
        if o['o_configured']:
            o.update(o_current_depth=self.config['depth'], o_current_context_id=self.config['context_id'],
                     o_total_iterations=self.config['total'])
        valid = safe and ((self.state == 'issue' and self.pacing == 0) or
                          (self.state in ('pause', 'abort') and self.presented))
        if valid:
            o['o_iteration_valid'] = 1
            o.update({'o_iteration_' + k: value for k, value in self.coordinate().items()})
        if safe and self.state == 'record':
            n = self.config
            o.update(o_completion_valid=1, o_completion_event_enable=n['completion_event_enable'],
                o_completion_event_id=n['completion_event_id'], o_completion_context_id=n['context_id'],
                o_completion_run_id=self.run_id, o_completion_status=self.completion,
                o_completion_iterations=self.accepted)
        o['o_quiesce_request'] = int(safe and (self.state == 'complete' or
                                             (self.state in ('pause', 'abort') and not self.presented)))
        o['o_quiescent'] = int(o['o_idle'] and not any(o[f'o_{group}_ready'] and v[f'i_{group}_valid'] == 1
                                                    for group in ('config', 'start', 'control')))
        if safe:
            o.update(self.events)
        return o

    def step(self, p):
        v = {k: number(raw) for k, raw in p.items()}
        if v['i_rstb'] == 0:
            self.reset()
            return
        if v['i_rstb'] != 1:
            return
        if v['i_flush'] == 1:
            epoch, fatal = self.epoch + 1, self.fatal
            self.reset()
            self.epoch = epoch % (1 << self.c.CONFIG_EPOCH_WIDTH)
            self.fatal = fatal
            return
        if v['i_flush'] != 0:
            return
        if self.fault:
            self.fatal = 1
            if not self.error:
                self.error = self.fault
            return
        if self.fatal:
            return
        o = self.outputs(p)
        old_state = self.state
        old_candidate = self.candidate
        idle = old_state == 'idle' and old_candidate is None
        error = 0
        events = {}
        if old_candidate is not None:
            config, error = decode(old_candidate, self.c)
            self.candidate = None
            if error:
                events['o_config_rejected'] = 1
            else:
                self.config = config
                self.epoch = (self.epoch + 1) % (1 << self.c.CONFIG_EPOCH_WIDTH)
                events['o_config_accepted'] = 1
        if o['o_config_ready'] and v['i_config_valid'] == 1:
            self.candidate = p.copy()
        if o['o_start_ready'] and v['i_start_valid'] == 1:
            if self.config and v['i_start_context_id'] == self.config['context_id'] and v['i_start_run_id'] is not None:
                self.run_id = v['i_start_run_id']
                self.accepted = self.pacing = 0
                self.points = cartesian(self.config['trip_count'][:self.config['depth']])
                self.point = next(self.points, None)
                self.state = 'issue' if self.config['total'] else 'record'
                self.completion = 0
                events['o_start_accepted'] = 1
                if not self.config['total']:
                    events['o_event_run_complete'] = 1
            else:
                error = 12
                events['o_start_rejected'] = 1
        transfer = o['o_iteration_valid'] and v['i_iteration_ready'] == 1
        last = transfer and self.accepted + 1 == self.config['total']
        if old_state == 'issue' and self.pacing:
            self.pacing -= 1
        if transfer:
            self.accepted += 1
            self.pacing = self.config['initiation_interval'] - 1
            self.presented = False
            events['o_event_iteration_transfer'] = 1
            if last:
                if old_state != 'abort':
                    self.state = 'complete'
            else:
                self.point = next(self.points)
                # Multiples of each rectangular prefix identify boundary crossings.
                wraps = sum(1 << k for k in range(self.config['depth'])
                            if self.accepted % prod(self.config['trip_count'][:k + 1]) == 0)
                events['o_event_outer_wrap'] = wraps
                events['o_event_inner_wrap'] = wraps & 1
        if o['o_iteration_valid'] and v['i_iteration_ready'] == 0:
            events['o_event_iteration_stall'] = 1
        accepted_abort = False
        if o['o_control_ready'] and v['i_control_valid'] == 1:
            cmd = v['i_control_command']
            owner = self.config and v['i_control_context_id'] == self.config['context_id'] and v['i_control_run_id'] == self.run_id
            legal = owner and ((cmd == 0 and self.c.SUPPORT_SUSPEND and old_state == 'issue') or
                (cmd == 1 and self.c.SUPPORT_SUSPEND and old_state == 'suspended') or
                (cmd == 2 and self.c.SUPPORT_ABORT and old_state in ('issue', 'pause', 'suspended')))
            if legal:
                events['o_control_accepted'] = 1
                if cmd == 0:
                    if not last:
                        self.state = 'pause'
                        self.presented = bool(o['o_iteration_valid'] and not transfer)
                elif cmd == 1:
                    self.state = 'issue'
                    events['o_event_resume'] = 1
                else:
                    accepted_abort = True
                    self.state = 'abort'
                    self.presented = bool(o['o_iteration_valid'] and not transfer)
            else:
                error = 13
                events['o_control_rejected'] = 1
        if o['o_quiesce_request'] and v['i_execution_quiescent'] == 1:
            if old_state == 'pause' and not accepted_abort:
                self.state = 'suspended'
                events['o_event_pause'] = 1
            else:
                self.state = 'record'
                self.completion = int(old_state == 'abort' or accepted_abort)
                events['o_event_abort' if self.completion else 'o_event_run_complete'] = 1
        if o['o_completion_valid'] and v['i_completion_ready'] == 1:
            self.state = 'idle'
            self.run_id = self.accepted = self.pacing = self.completion = 0
        controls = ('i_rstb', 'i_flush', 'i_error_clear', 'i_config_valid', 'i_start_valid',
                    'i_control_valid', 'i_iteration_ready', 'i_completion_ready', 'i_execution_quiescent')
        if any(v[name] is None for name in controls):
            error = 1
        if idle and v['i_error_clear'] == 1:
            self.error = 0
        elif not self.error:
            self.error = error
        self.events = events
