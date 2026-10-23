"""Clock opportunities and passive observations, including four-state values."""

from dataclasses import dataclass

from pyuvm import uvm_sequence_item

INPUTS = (
    "i_rstb",
    "i_clock_enable",
    "i_valid",
    "i_lane_enable",
    "i_predicate_enable",
    "i_execute_predicate",
    "i_select_predicate",
    "i_opcode",
    "i_operand_a",
    "i_operand_b",
    "i_accumulator",
    "i_signed",
    "i_saturate",
)
OUTPUTS = (
    "o_valid",
    "o_write_enable",
    "o_suppressed",
    "o_illegal_operation",
    "o_result",
    "o_result_format",
    "o_result_signed",
    "o_predicate_valid",
    "o_predicate",
    "o_carry",
    "o_borrow",
    "o_overflow",
    "o_saturated",
    "o_zero",
    "o_negative",
)


class LaneItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: LaneItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    value: str
