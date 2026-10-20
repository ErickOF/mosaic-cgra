"""Set-based join expectations and queues populated only by actual handshakes."""

from collections import deque
from mosaic_uvm.logic import bits


def known(word):
    return set(word) <= {'0', '1'}


def lane(word, index, width):
    end = len(word)-index*width
    return word[end-width:end]


def required_inputs(config, ports):
    mask = int(ports['i_required'], 2) if config.masked else config.all_inputs
    return {k for k in range(config.inputs) if mask & (1 << k)}


def expected_outputs(config, ports):
    required = required_inputs(config, ports)
    present = {k for k in required if ports['i_valid'][-k-1] == '1'}
    missing = required-present
    valid = bool(required) and not missing
    # Set subtraction expresses each ready independently of its own valid.
    ready = sum(1 << k for k in required if not (missing-{k}) and ports['i_ready'] == '1')
    words = [lane(ports['i_data'], k, config.width) if valid and k in required else '0'*config.width
        for k in range(config.inputs)]
    return dict(o_valid=str(int(valid)), o_ready=bits(ready, config.inputs),
        o_required=bits(sum(1 << k for k in required) if valid else 0, config.inputs),
        o_data=''.join(reversed(words)))


class StreamJoinModel:
    def __init__(self, config):
        self.config = config
        self.queues = [deque() for _ in range(config.inputs)]
        self.accepted = [0]*config.inputs
        self.joined = self.edges = 0

    def sample_edge(self, ports, intentional):
        self.edges += 1
        selected = required_inputs(self.config, ports)
        accepted = {k for k in range(self.config.inputs)
            if ports['i_valid'][-k-1] == '1' and ports['o_ready'][-k-1] == '1'}
        output_accept = ports['o_valid'] == '1' and ports['i_ready'] == '1'
        assert accepted == (selected if output_accept else set()), 'Atomicity assertion failed'
        for k in accepted:
            word = lane(ports['i_data'], k, self.config.width)
            assert intentional or known(word), 'Protocol assertion failed: accepted_data'
            self.queues[k].append((self.edges, word))
            self.accepted[k] += 1
        if output_accept:
            assert selected and int(ports['o_required'], 2) == sum(1 << k for k in selected), 'Joined-mask assertion failed'
            for k in selected:
                edge, word = self.queues[k].popleft()
                assert edge == self.edges, 'Join added latency or reordered operands'
                assert lane(ports['o_data'], k, self.config.width) == word, 'Joined-data assertion failed'
            self.joined += 1
        assert all(not queue for queue in self.queues), 'Join left a partially consumed operation'
        return accepted, output_accept
