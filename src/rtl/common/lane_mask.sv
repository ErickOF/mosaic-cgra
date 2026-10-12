`timescale 1ns / 1ps

// Combine vector-operation controls into one canonical per-lane decision.
module lane_mask #(
    parameter int unsigned LANES = 4
) (
    input  logic             i_operation_valid,
    input  logic [LANES-1:0] i_lane_valid,
    input  logic [LANES-1:0] i_lane_mask,
    input  logic [LANES-1:0] i_lane_predicate,
    output logic [LANES-1:0] o_lane_active,
    output logic [LANES-1:0] o_lane_isolate,
    output logic [LANES-1:0] o_lane_write_mask
);
    if (LANES < 1) begin : gen_invalid_lanes
        initial $fatal(1, "LANES must be greater than or equal to one");
    end

    always_comb begin
        o_lane_active = {LANES{i_operation_valid}} & i_lane_valid & i_lane_mask & i_lane_predicate;
        o_lane_isolate = ~o_lane_active;
        o_lane_write_mask = o_lane_active;
    end
endmodule
