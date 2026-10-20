"""Independent token/bubble history with explicit acceptance and cancellation."""

from mosaic_uvm.logic import bits


def known(word):
    return not (set(word) & set('xz'))


def fields(word, width):
    return [word[len(word)-(c+1)*width:len(word)-c*width] for c in range(len(word)//width)]


def pack(values, width):
    return ''.join(bits(value, width) for value in reversed(values))


def protocol_violation(config, ports):
    for name in ('i_rstb', 'i_advance', 'i_channel_enable', 'i_flush'):
        if not known(ports[name]):
            return name
    if ports['i_rstb'] == '0':
        return None
    for c, delay in enumerate(fields(ports['i_delay'], config.delay_width)):
        if ports['i_channel_enable'][-c-1] == '0':
            continue
        if not known(delay):
            return 'i_delay'
        if ports['i_advance'] == '1' and ports['i_flush'][-c-1] == '0' and int(delay, 2) <= config.capacities[c]:
            valid = ports['i_input_valid'][-c-1]
            if not known(valid):
                return 'i_input_valid'
            if valid == '1' and not known(fields(ports['i_input_data'], config.width)[c]):
                return 'i_input_data'
    return None


class RduModel:
    def __init__(self, config):
        self.config = config
        self.initialized = False
        self.history = [[None]*capacity for capacity in config.capacities]
        self.raw_data = ['x'*config.width for _ in range(max(1, config.total))]
        self.previous_delay = None
        self.accepted = [0]*config.channels
        self.transferred = [0]*config.channels
        self.discarded = [0]*config.channels

    def reset(self, ports):
        self.initialized = True
        for c, line in enumerate(self.history):
            self.discarded[c] += sum(token is not None for token in line)
            line[:] = [None]*len(line)
        self.previous_delay = fields(ports['i_delay'], self.config.delay_width)

    def boundaries(self, ports):
        boundaries = set()
        current = fields(ports['i_delay'], self.config.delay_width)
        if self.previous_delay is None:
            return boundaries
        for c, (old, new) in enumerate(zip(self.previous_delay, current)):
            if old != new:
                if ports['i_rstb'] == '0':
                    boundaries.add('reset')
                elif ports['i_flush'][-c-1] == '1':
                    boundaries.add('flush')
                else:
                    assert not any(token is not None for token in self.history[c]), 'Protocol assertion failed: delay_boundary'
                    boundaries.add('empty')
        return boundaries

    def step(self, ports):
        config = self.config
        delays = fields(ports['i_delay'], config.delay_width)
        data = fields(ports['i_input_data'], config.width)
        records = []
        for c, old in enumerate(self.history):
            delay = int(delays[c], 2) if known(delays[c]) else None
            enabled = ports['i_channel_enable'][-c-1] == '1'
            legal = delay is not None and delay <= len(old)
            advance = ports['i_advance'] == '1'
            flush = ports['i_flush'][-c-1] == '1'
            incoming, consumed = None, None
            before = tuple(old)
            if flush:
                self.discarded[c] += sum(token is not None for token in old)
                old[:] = [None]*len(old)
            elif enabled and legal and advance:
                incoming = data[c] if ports['i_input_valid'][-c-1] == '1' else None
                if delay == 0:
                    consumed = incoming
                else:
                    consumed = before[delay-1]
                    old[:delay] = [incoming, *before[:delay-1]]
                    # Invalid stages retain payload even though validity moves.
                    for stage, token in enumerate(old[:delay]):
                        if token is not None:
                            self.raw_data[config.bases[c]+stage] = token
                self.accepted[c] += int(incoming is not None)
                self.transferred[c] += int(consumed is not None)
            records.append(dict(channel=c, delay=delay, enabled=enabled, legal=legal, advance=advance,
                flush=flush, input_valid=ports['i_input_valid'][-c-1], before=before,
                after=tuple(old), incoming=incoming, consumed=consumed))
        self.previous_delay = delays
        self.conservation()
        return records

    def conservation(self):
        for c, line in enumerate(self.history):
            assert self.accepted[c] == self.transferred[c] + self.discarded[c] + sum(token is not None for token in line), \
                f'Token-conservation assertion failed: channel {c}'

    def outputs(self, ports):
        config = self.config
        data_in = fields(ports['i_input_data'], config.width)
        data, valid, transfer, error, empty = [], [], [], [], []
        for c, delay_word in enumerate(fields(ports['i_delay'], config.delay_width)):
            enabled = ports['i_channel_enable'][-c-1]
            legal = int(delay_word, 2) <= config.capacities[c] if known(delay_word) else None
            error.append('0' if enabled == '0' else 'x' if legal is None else str(int(not legal)))
            empty.append(int(not any(token is not None for token in self.history[c])))
            word, present = '0'*config.width, '0'
            if ports['i_rstb'] == '1' and ports['i_flush'][-c-1] == '0' and enabled == '1':
                if legal is None:
                    word, present = 'x'*config.width, 'x'
                elif legal:
                    delay = int(delay_word, 2)
                    token = data_in[c] if delay == 0 and ports['i_input_valid'][-c-1] == '1' else \
                        self.history[c][delay-1] if delay > 0 else None
                    if delay == 0 and not known(ports['i_input_valid'][-c-1]):
                        word, present = 'x'*config.width, 'x'
                    elif token is not None:
                        word, present = token, '1'
            data.append(word)
            valid.append(present)
            transfer.append('0' if ports['i_advance'] == '0' else present)
        return dict(o_output_data=pack(data, config.width), o_output_valid=pack(valid, 1),
            o_output_transfer=pack(transfer, 1), o_channel_empty=pack(empty, 1),
            o_all_empty=str(int(all(empty))), o_config_error=pack(error, 1))
