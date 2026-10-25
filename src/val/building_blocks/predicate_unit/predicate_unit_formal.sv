`timescale 1ns / 1ps

// Two-state sequential refinement. Valid data and every validity/response bit
// form the induction invariant; uninitialized invalid data is unconstrained.
module predicate_unit_formal #(
    parameter int D = 4,
    parameter int N = 4,
    parameter int ASYNC_RESET = 0,
    localparam int AW = D > 1 ? $clog2(D) : 1,
    localparam int B = 3 * N + 5
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [3:0] i_opcode,
    input logic [N-1:0] i_lane_mask,
    input logic [AW-1:0] i_source_a_addr,
    input logic [AW-1:0] i_source_b_addr,
    input logic [AW-1:0] i_destination_addr,
    input logic [N-1:0] i_predicate_input,
    input logic i_write_enable,
    input logic o_valid,
    input logic [N-1:0] o_result,
    input logic [N-1:0] o_result_valid,
    input logic o_any,
    input logic o_all,
    input logic [N-1:0] o_updated_mask,
    input logic o_invalidated,
    input logic o_illegal_operation,
    input logic [D*N-1:0] actual_data,
    input logic [D*N-1:0] actual_valid
);
    wire [B-1:0] response;
    wire [B-1:0] next_response;
    wire [D*N-1:0] data;
    wire [D*N-1:0] validity;
    wire legal;
    wire [B-1:0] actual = {o_valid, o_result, o_result_valid, o_any, o_all,
        o_updated_mask, o_invalidated, o_illegal_operation};
    bit initialized = 1'b0;
    predicate_unit_reference #(.D(D), .N(N), .ASYNC_RESET(ASYNC_RESET)) reference_unit (.*);

    always @(posedge i_clk) begin
        if (!i_rstb) initialized <= 1'b1;
    end

    always_comb begin
        if (initialized) begin
            assert (actual == response);
            for (int entry = 0; entry < D; entry++) begin
                assert (actual_valid[entry*N+:N] == validity[entry*N+:N]);
                assert (((actual_data[entry*N+:N] ^ data[entry*N+:N]) & validity[entry*N+:N]) == 0);
            end
        end
        if (ASYNC_RESET == 1 && !i_rstb) begin
            assert (actual == 0);
            for (int entry = 0; entry < D; entry++) assert (actual_valid[entry*N+:N] == 0);
        end
    end
endmodule
