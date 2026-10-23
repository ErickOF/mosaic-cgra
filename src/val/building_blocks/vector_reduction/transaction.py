"""Reuse generic clock opportunities and observations with reduction port names."""

from vector_lane.transaction import LaneItem as ReductionItem
from vector_lane.transaction import Observation

INPUTS = ("i_rstb", "i_clock_enable", "i_valid", "i_opcode", "i_element_mask", "i_data", "i_signed")
OUTPUTS = (
    "o_valid",
    "o_result",
    "o_result_format",
    "o_result_signed",
    "o_active_count",
    "o_zero",
    "o_negative",
    "o_illegal_operation",
)
__all__ = ["INPUTS", "OUTPUTS", "Observation", "ReductionItem"]
