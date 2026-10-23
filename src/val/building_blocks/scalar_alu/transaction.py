"""Four-state combinational requests and passive port observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = (
    'i_enable',
    'i_opcode',
    'i_operand_a',
    'i_operand_b',
    'i_predicate',
    'i_signed',
    'i_saturate',
)
OUTPUTS = (
    'o_result',
    'o_predicate',
    'o_zero',
    'o_negative',
    'o_carry',
    'o_borrow',
    'o_overflow',
    'o_saturated',
    'o_illegal_operation',
)


class AluItem(uvm_sequence_item):
    def __init__(self, label, ports, *, random=False, exhaustive=False):
        super().__init__(label)
        self.ports = ports
        self.random = random
        self.exhaustive = exhaustive


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: AluItem
    stage: str
