"""Arbitrary-precision architectural state; no RTL-sized arithmetic or mux reuse."""

from mosaic_uvm.logic import bits


def known(word):
    return not (set(word) & set('xz'))


def fields(word, width):
    return [word[len(word)-(index+1)*width:len(word)-index*width] for index in range(len(word)//width)]


def pack(values, width):
    return ''.join(bits(value, width) for value in reversed(values))


def configurations(config, ports):
    return list(zip(fields(ports['i_event_select'], config.event_address_width),
        reversed(ports['i_threshold_enable']), fields(ports['i_threshold_value'], config.width)))


def protocol_violation(config, ports):
    for name in ('i_rstb', 'i_global_enable', 'i_freeze', 'i_counter_enable', 'i_clear', 'i_read_enable'):
        if not known(ports[name]):
            return name
    if ports['i_rstb'] == '0':
        return None
    if not config.snapshot:
        if ports['i_snapshot'] != '0' or ports['i_read_snapshot'] != '0':
            return 'unsupported_snapshot'
    elif not known(ports['i_snapshot']):
        return 'i_snapshot'
    if not config.threshold:
        if set(ports['i_threshold_enable'] + ports['i_threshold_value']) != {'0'}:
            return 'unsupported_threshold'
    elif not known(ports['i_threshold_enable']):
        return 'i_threshold_enable'
    for c, (selection, enabled, threshold) in enumerate(configurations(config, ports)):
        if config.threshold and enabled == '1' and not known(threshold):
            return 'i_threshold_value'
        if ports['i_global_enable'] == '1' and ports['i_counter_enable'][-c-1] == '1':
            if not known(selection):
                return 'i_event_select'
            e = int(selection, 2)
            if e < config.events and ports['i_freeze'] == '0' and ports['i_clear'][-c-1] == '0':
                if config.threshold and enabled == '1' and int(threshold, 2) == 0:
                    continue  # Known invalid configuration is rejected by hardware.
                valid = ports['i_event_valid'][-e-1]
                if not known(valid):
                    return 'i_event_valid'
                if valid == '1' and not known(fields(ports['i_event_increment'], config.increment_width)[e]):
                    return 'i_event_increment'
    if ports['i_read_enable'] == '1':
        if not known(ports['i_read_index']):
            return 'i_read_index_unknown'
        if int(ports['i_read_index'], 2) >= config.counters:
            return 'i_read_index_range'
        if not known(ports['i_read_snapshot']):
            return 'i_read_snapshot'
    return None


class PerformanceCountersModel:
    def __init__(self, config):
        self.config = config
        self.initialized = False
        self.shadow = self.shadow_overflow = None
        self.previous_configuration = None

    def reset(self, ports):
        self.initialized = True
        self.live = [0] * self.config.counters
        self.overflow = [0] * self.config.counters
        self.pulses = [0] * self.config.counters
        self.snapshot_valid = False
        self.previous_configuration = configurations(self.config, ports)

    def configuration_error(self, ports, c):
        if ports['i_global_enable'] == '0' or ports['i_counter_enable'][-c-1] == '0':
            return '0'
        selection, enabled, threshold = configurations(self.config, ports)[c]
        if not known(selection):
            return 'x'
        if int(selection, 2) >= self.config.events:
            return '1'
        if self.config.threshold and enabled != '0':
            if enabled != '1' or not known(threshold):
                return 'x'
            return str(int(int(threshold, 2) == 0))
        return '0'

    def configuration_changes(self, ports):
        current = configurations(self.config, ports)
        boundaries = []
        for c, (old, new) in enumerate(zip(self.previous_configuration, current)):
            if old != new:
                if ports['i_clear'][-c-1] == '1':
                    boundaries.append('clear')
                else:
                    assert ports['i_counter_enable'][-c-1] == '0' and self.live[c] == 0 and self.overflow[c] == 0, \
                        'Protocol assertion failed: configuration_boundary'
                    boundaries.append('disabled_clear')
        self.previous_configuration = current
        return boundaries

    def step(self, ports):
        config = self.config
        records = []
        for c, (selection, enabled, threshold_word) in enumerate(configurations(config, ports)):
            old, sticky = self.live[c], self.overflow[c]
            selected = int(selection, 2) if known(selection) else None
            active = ports['i_global_enable'] == '1' and ports['i_counter_enable'][-c-1] == '1'
            legal = self.configuration_error(ports, c) == '0'
            valid = bool(selected is not None and selected < config.events and ports['i_event_valid'][-selected-1] == '1')
            amount = int(fields(ports['i_event_increment'], config.increment_width)[selected], 2) if active and legal and valid and ports['i_freeze'] == '0' else 0
            requested = active and legal and valid and ports['i_freeze'] == '0' and amount > 0
            clear = ports['i_clear'][-c-1] == '1'
            pulse, overflow, total = 0, False, old
            if clear:
                self.live[c], self.overflow[c] = 0, 0
            elif requested:
                total = old + amount  # Python integer retains every increment bit.
                overflow = total > config.maximum
                self.live[c] = min(config.maximum, total) if config.saturate else total % (config.maximum + 1)
                self.overflow[c] = int(bool(sticky or overflow))
                if config.threshold and enabled == '1':
                    threshold = int(threshold_word, 2)
                    comparison = self.live[c] if config.saturate else total
                    pulse = int(old < threshold <= comparison)
            self.pulses[c] = pulse
            records.append(dict(counter=c, selected=selected, active=active, legal=legal, valid=valid,
                amount=amount, requested=requested, clear=clear, old=old, value=self.live[c],
                old_overflow=sticky, overflow=overflow, sticky=self.overflow[c], pulse=pulse,
                threshold=int(threshold_word, 2) if config.threshold and enabled == '1' else None,
                total=total))
        if config.snapshot and ports['i_snapshot'] == '1':
            self.shadow, self.shadow_overflow = self.live.copy(), self.overflow.copy()
            self.snapshot_valid = True
        return records

    def outputs(self, ports):
        config = self.config
        data, overflow, valid = '0'*config.width, '0', '0'
        if ports['i_read_enable'] == '1':
            if not known(ports['i_read_index']):
                data, overflow, valid = 'x'*config.width, 'x', 'x'
            elif int(ports['i_read_index'], 2) < config.counters:
                index = int(ports['i_read_index'], 2)
                if ports['i_read_snapshot'] == '0':
                    data, overflow, valid = bits(self.live[index], config.width), str(self.overflow[index]), '1'
                elif ports['i_read_snapshot'] == '1':
                    if config.snapshot and self.snapshot_valid:
                        data, overflow, valid = bits(self.shadow[index], config.width), str(self.shadow_overflow[index]), '1'
                else:
                    data, overflow, valid = 'x'*config.width, 'x', 'x'
        return dict(o_read_data=data, o_read_overflow=overflow, o_read_valid=valid,
            o_counter_overflow=pack(self.overflow, 1), o_threshold_event=pack(self.pulses, 1),
            o_config_error=''.join(self.configuration_error(ports, c) for c in reversed(range(config.counters))),
            o_snapshot_valid=str(int(self.snapshot_valid)))
