"""Physical level acknowledgements and a tagged package/endpoint validation authority."""
from collections import deque
from cluster_power_manager.config import WIDTHS, pack, unpack


class PhysicalPeers:
    def __init__(self, rng):
        self.rng = rng
        self.ack_latency = 1
        self.history = deque()
        self.requests = deque()
        self.delay = 2
        self.validation_status = 0
        self.validation_flags = 15
        self.block = set()
        self.overrides = {}
        self.foreign = deque()
        self.cycle = 0
        self.held_response = None

    def drive(self, ports, previous, parameters):
        if previous is not None:
            self.history.append(previous.copy())
        observed = self.history[0] if self.history else None
        if len(self.history) > self.ack_latency:
            observed = self.history.popleft()
        if observed is not None:
            ports['i_isolation_ack'] = observed['o_isolation_enable']
            ports['i_reset_ack'] = observed['o_cluster_reset_request']
            ports['i_boundary_endpoint_ack'] = observed['o_boundary_endpoint_enable']
            ports['i_clock_stopped'] = int(not observed['o_cluster_clock_enable'])
        ports['i_revalidate_ready'] = int('request' not in self.block)
        if self.held_response is None and 'response' not in self.block:
            if self.foreign:
                self.held_response = self.foreign.popleft()
            elif self.requests and self.requests[0][0] <= self.cycle:
                self.held_response = self.requests.popleft()[1]
        ports['i_revalidate_response_valid'] = int(self.held_response is not None)
        ports['i_revalidate_response_record'] = self.held_response or 0
        ports.update(self.overrides)

    def observe(self, p):
        if p['i_revalidate_response_valid'] and p['o_revalidate_response_ready']:
            self.held_response = None
        if p['o_revalidate_valid'] and p['i_revalidate_ready']:
            request = unpack('validation', p['o_revalidate_record'])
            response = {n: request[n] for n in ('identity', 'boot_generation', 'serial', 'tag')}
            response |= dict(status=self.validation_status, validity=self.validation_flags)
            self.requests.append((self.cycle + self.delay, pack('validation_response', **response)))
        self.cycle += 1

    def global_reset(self):
        self.requests.clear()
        self.held_response = None
        self.history.clear()
        self.foreign.clear()
