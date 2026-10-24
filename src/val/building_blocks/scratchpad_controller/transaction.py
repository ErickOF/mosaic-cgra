"""Public packed interface and cycle transactions; no DUT state drives stimulus."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

CONTROLS = dict(i_clk=1, i_rstb=1, i_flush=1, i_error_clear=1, i_perm_valid=1,
                i_read_permission='P', i_write_permission='P')
PORTS = {name: ('input', width) for name, width in CONTROLS.items()}
PORTS.update(o_perm_ready=('output', 1), o_permission_updated=('output', 1))
for side, direction, kind, count in (('client', 'input', 'req', 'C'),
        ('client', 'output', 'rsp', 'C'), ('bank', 'output', 'req', 'B'),
        ('bank', 'input', 'rsp', 'B')):
    fields = dict(valid=1, write=1)
    fields.update(dict(address='A' if side == 'client' else 'L', size_log2='S',
                       wdata='D', wstrobe='Y') if kind == 'req' else dict(rdata='D'))
    fields['tag'] = 'T' if side == 'client' else 'K'
    if kind == 'rsp':
        fields.update(error=1, error_code=4, corrected=1, uncorrectable=1)
    PORTS.update({f"{'i' if direction == 'input' else 'o'}_{side}_{kind}_{name}":
                  (direction, (count, width)) for name, width in fields.items()})
    PORTS[f"{'o' if direction == 'input' else 'i'}_{side}_{kind}_ready"] = (
        'output' if direction == 'input' else 'input', count)
PORTS.update(o_bank_flush=('output', 'B'), i_bank_flush_completed=('input', 'B'),
             i_bank_idle=('input', 'B'), o_idle=('output', 1), o_busy=('output', 1),
             o_flushing=('output', 1), o_flush_completed=('output', 1),
             o_client_outstanding=('output', ('C', 'O')), o_bank_conflict=('output', 'B'),
             o_request_accepted=('output', 'C'), o_response_accepted=('output', 'C'),
             o_permission_denied=('output', 'C'), o_error=('output', 1), o_error_code=('output', 4))
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
REQ_FIELDS = ('write', 'address', 'size_log2', 'wdata', 'wstrobe', 'tag')
RSP_FIELDS = ('write', 'rdata', 'tag', 'error', 'error_code', 'corrected', 'uncorrectable')


class ControllerItem(uvm_sequence_item):
    def __init__(self, label, clients, controls, *, edge=True, random=False, peer=None):
        super().__init__(label)
        self.clients = clients
        self.controls = controls
        self.edge = edge
        self.random = random
        self.peer = peer or {}
        self.pre = self.post = None


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: ControllerItem
    stage: str
