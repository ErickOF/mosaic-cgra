"""External array/service response agents with adversarial latency and identities.

These are Python peers, not hidden RTL implementations of the array or system.
A terminal may be delayed beyond timeout; the original identity is retained.
"""
from collections import deque
from runtime_controller.config import WIDTHS, CODES, pack, unpack
from runtime_controller.model import lane


class Peers:
    def __init__(self, rng):
        self.rng = rng
        self.pending = [deque() for _ in range(7)]
        self.rule = None
        self.delay = None
        self.block = set()
        self.random_ready = False
        self.foreign = deque()
        self.last = None
        self.cycle = 0
        self.immediate = False
        self.present = None
        self.immediate_responses = {}

    def drive(self, ports):
        self.immediate_responses = {}
        ports['i_array_runtime_ready'] = int(6 not in self.block and
            (not self.random_ready or self.rng.randrange(4) != 0))
        ports['i_service_ready'] = sum(int(ep not in self.block and
            (not self.random_ready or self.rng.randrange(4) != 0)) << ep for ep in range(6))
        ports['i_array_runtime_response_valid'] = 0
        ports['i_array_runtime_response_record'] = 0
        ports['i_service_response_valid'] = 0
        ports['i_service_response_record'] = 0
        for ep, queue in enumerate(self.pending):
            if queue and queue[0][0] <= self.cycle:
                self._drive_response(ports, ep, queue[0][1])
        if self.foreign:
            ep, bits = self.foreign[0]
            # A foreign terminal never overwrites a real endpoint's held response.
            prefix = 'array_runtime' if ep == 6 else 'service'
            index = 0 if ep == 6 else ep
            if not (ports[f'i_{prefix}_response_valid'] >> index & 1):
                self._drive_response(ports, ep, bits)

        if self.immediate and self.present is not None:
            for ep in range(7):
                prefix = 'array_runtime' if ep == 6 else 'service'
                index = 0 if ep == 6 else ep
                if self.present[f'o_{prefix}_valid'] >> index & 1 and \
                        ports[f'i_{prefix}_ready'] >> index & 1:
                    action = unpack('action', lane(self.present[f'o_{prefix}_record'], index,
                                                   WIDTHS['action']))
                    response = {k: action[k] for k in ('identity', 'command', 'cluster_mask', 'tag')}
                    bits = pack('ack', **(response | dict(status=CODES['ack_status']['OK'], flags=3)))
                    self._drive_response(ports, ep, bits)
                    self.immediate_responses[ep] = bits

    @staticmethod
    def _drive_response(ports, ep, bits):
        if ep == 6:
            ports['i_array_runtime_response_valid'] = 1
            ports['i_array_runtime_response_record'] = bits
        else:
            ports['i_service_response_valid'] |= 1 << ep
            ports['i_service_response_record'] |= bits << (ep * WIDTHS['ack'])

    def observe(self, p):
        for ep in range(7):
            prefix = 'array_runtime' if ep == 6 else 'service'
            index = 0 if ep == 6 else ep
            if p[f'i_{prefix}_response_valid'] >> index & p[f'o_{prefix}_response_ready'] >> index & 1:
                bits = lane(p[f'i_{prefix}_response_record'], index, WIDTHS['ack'])
                queue = self.pending[ep]
                if queue and queue[0][1] == bits:
                    queue.popleft()
                    self.last = (ep, bits)
                elif self.foreign and self.foreign[0] == (ep, bits):
                    self.foreign.popleft()
            if p[f'o_{prefix}_valid'] >> index & p[f'i_{prefix}_ready'] >> index & 1:
                action = unpack('action', lane(p[f'o_{prefix}_record'], index, WIDTHS['action']))
                response = {k: action[k] for k in ('identity', 'command', 'cluster_mask', 'tag')}
                response |= dict(status=CODES['ack_status']['OK'], error=0, flags=3)
                if self.rule:
                    response.update(self.rule(ep, action) or {})
                delay = self.delay(ep, action) if self.delay else self.rng.randrange(1, 5)
                if ep in self.immediate_responses:
                    self.last = (ep, self.immediate_responses[ep])
                else:
                    self.pending[ep].append((self.cycle + delay, pack('ack', **response)))
        self.cycle += 1

    def recover_system(self):
        """Explicit global system cleanup; local controller reset cannot call this implicitly."""
        for queue in self.pending:
            queue.clear()
        self.foreign.clear()
        self.last = None
