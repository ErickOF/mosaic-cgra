"""Clock opportunities and four-state samples use the existing generic records."""

from vector_lane.transaction import LaneItem as PredicateItem
from vector_lane.transaction import Observation

INPUTS = (
    "i_rstb",
    "i_clock_enable",
    "i_valid",
    "i_opcode",
    "i_lane_mask",
    "i_source_a_addr",
    "i_source_b_addr",
    "i_destination_addr",
    "i_predicate_input",
    "i_write_enable",
)
OUTPUTS = (
    "o_valid",
    "o_result",
    "o_result_valid",
    "o_any",
    "o_all",
    "o_updated_mask",
    "o_invalidated",
    "o_illegal_operation",
)
__all__ = ["INPUTS", "OUTPUTS", "Observation", "PredicateItem"]
