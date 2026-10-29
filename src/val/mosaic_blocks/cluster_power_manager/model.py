"""Independent transaction, physical qualification and shutdown-order contracts."""
from collections import deque
from cluster_power_manager.config import CODES, WIDTHS, pack, unpack

STATE, PHASE, CMD, STATUS, ERROR = (CODES[k] for k in ('state','phase','command','status','error'))


def lane(value, index, width):
    return value >> (index * width) & ((1 << width) - 1)


def command_from_ports(p):
    identity = pack('identity', **{field: p.get(port) or 0 for field, port in dict(
        cluster_id='i_command_cluster_id', owner_id='i_command_owner_id',
        kernel_id='i_command_kernel_id', package_id='i_command_package_id',
        allocation_generation='i_command_allocation_generation', epoch='i_command_execution_epoch').items()})
    return dict(identity=identity, command=p['i_command'] or 0, target=p['i_command_target_state'] or 0,
                point=p['i_command_operating_point'] or 0, tag=p['i_command_tag'] or 0)


class CommandLedger:
    def __init__(self):
        self.pending = None
        self.accepted = 0
        self.completed = 0
        self.requests = {}
        self.seen_requests = set()

    def accept(self, request):
        assert self.pending is None, ('Command capacity exceeded', self.pending, request)
        self.pending = request
        self.accepted += 1

    def respond(self, response):
        assert self.pending is not None, ('Unsolicited terminal', response)
        assert all(response[n] == self.pending[n] for n in ('identity','command','tag'))
        self.pending = None
        self.completed += 1

    def validation_request(self, request):
        key = (request['boot_generation'], request['serial'])
        assert key not in self.seen_requests, ('Validation identity reused', key)
        self.seen_requests.add(key)
        self.requests[key] = request

    def validation_response(self, response):
        key = (response['boot_generation'], response['serial'])
        request = self.requests.get(key)
        if request is None or any(response[n] != request[n] for n in ('identity','tag')):
            return False
        del self.requests[key]
        return response['status'] == 0 and response['validity'] == 15


class PhysicalQualification:
    """Predict synchronized level histories without reading synchronizer internals."""
    def __init__(self, parameters):
        self.p = parameters
        self.pipelines = {}
        self.power_streak = 0
        self.clock_streak = 0
        self.supply_was_qualified = False
        self.previous_root = 0
        self.release = deque([0, 0])
        for name, depth in dict(i_power_good='POWER_GOOD_SYNC_STAGES',
                i_power_switch_ack='POWER_GOOD_SYNC_STAGES',
                i_clock_source_ready='CLOCK_STATUS_SYNC_STAGES',
                i_voltage_ready='VOLTAGE_STATUS_SYNC_STAGES').items():
            self.pipelines[name] = deque([0] * parameters[depth])

    def synchronized(self, p, name):
        return self.pipelines[name][-1] if self.p['ASYNC_PHYSICAL_STATUS'] else p[name]

    def step(self, p):
        good = (1 << self.p['NUM_POWER_SWITCH_GROUPS']) - 1
        powered = self.synchronized(p,'i_power_good') == good and \
            self.synchronized(p,'i_power_switch_ack') == good
        ready = self.synchronized(p,'i_clock_source_ready') == 1 and \
            self.synchronized(p,'i_voltage_ready') == 1
        if p['o_transition_phase'] == PHASE['POWER']:
            self.power_streak = self.power_streak + 1 if powered else 0
            self.supply_was_qualified |= self.power_streak >= self.p['POWER_STABLE_CYCLES']
        if p['o_cluster_clock_enable'] and not self.previous_root:
            assert powered, 'Root requested without synchronized power and switch status'
            assert self.supply_was_qualified, 'Root requested before full power qualification'
        if p['o_cluster_accept_enable']:
            assert p['o_state_valid']
        self.previous_root = p['o_cluster_clock_enable']
        effective_reset = not self.p['ASYNC_RESET'] or self.release[-1] == 1
        for name, pipeline in self.pipelines.items():
            pipeline.appendleft(p[name] if effective_reset else 0)
            pipeline.pop()
        self.release.appendleft(1)
        self.release.pop()


def complete_drain(p, parameters):
    scalars = ('i_cluster_quiescent','i_cluster_drain_done','i_scratchpad_idle',
               'i_memory_boundary_idle','i_local_network_idle','i_event_idle','i_configuration_idle',
               'i_counter_snapshot_idle','i_debug_idle','i_global_endpoint_drained')
    return (not p['i_cluster_busy'] and not p['i_tile_busy_mask'] and all(p[n] == 1 for n in scalars)
            and p['i_tile_quiescent_mask'] == (1 << parameters['NUM_TILES']) - 1
            and p['i_tile_drain_done_mask'] == (1 << parameters['NUM_TILES']) - 1
            and p['i_boundary_drained'] == (1 << parameters['NUM_BOUNDARY_ENDPOINTS']) - 1)
