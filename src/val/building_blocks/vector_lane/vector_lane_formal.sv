`timescale 1ns / 1ps

// Two-state mathematical equivalence. Registered profiles use an independent
// whole-response history, with arbitrary reset and CE after an initial reset.
module vector_lane_formal #(
    parameter ELEMENT_WIDTH = 8,
    parameter ACC_WIDTH = 32,
    parameter SUPPORT_MUL = 1,
    parameter SUPPORT_MAC = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter LANE_LATENCY = 1,
    parameter MUL_LATENCY = 1,
    parameter MAC_LATENCY = 1,
    parameter MAX_LANE_LATENCY = 4,
    parameter ASYNC_RESET = 0,
    parameter OPCODE_WIDTH = 5,
    parameter RESULT_FORMAT_WIDTH = 2
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic i_lane_enable,
    input logic i_predicate_enable,
    input logic i_execute_predicate,
    input logic i_select_predicate,
    input logic [4:0] i_opcode,
    input logic [ELEMENT_WIDTH-1:0] i_operand_a,
    input logic [ELEMENT_WIDTH-1:0] i_operand_b,
    input logic [ACC_WIDTH-1:0] i_accumulator,
    input logic i_signed,
    input logic i_saturate,
    output wire o_valid,
    output wire o_write_enable,
    output wire o_suppressed,
    output wire o_illegal_operation,
    output wire [ACC_WIDTH-1:0] o_result,
    output wire [1:0] o_result_format,
    output wire o_result_signed,
    output wire o_predicate_valid,
    output wire o_predicate,
    output wire o_carry,
    output wire o_borrow,
    output wire o_overflow,
    output wire o_saturated,
    output wire o_zero,
    output wire o_negative
);
    localparam int A = ACC_WIDTH;
    localparam int L = LANE_LATENCY;
    vector_lane #(
        .ELEMENT_WIDTH(ELEMENT_WIDTH),
        .ACC_WIDTH(ACC_WIDTH),
        .SUPPORT_MUL(SUPPORT_MUL),
        .SUPPORT_MAC(SUPPORT_MAC),
        .SUPPORT_SATURATION(SUPPORT_SATURATION),
        .SUPPORT_MINMAX(SUPPORT_MINMAX),
        .LANE_LATENCY(LANE_LATENCY),
        .MUL_LATENCY(MUL_LATENCY),
        .MAC_LATENCY(MAC_LATENCY),
        .MAX_LANE_LATENCY(MAX_LANE_LATENCY),
        .ASYNC_RESET(ASYNC_RESET),
        .OPCODE_WIDTH(OPCODE_WIDTH),
        .RESULT_FORMAT_WIDTH(RESULT_FORMAT_WIDTH)
    ) dut (.*);
    wire [A+14:0] reference_now;
    wire [A+14:0] actual = {o_valid, o_write_enable, o_suppressed, o_illegal_operation,
        o_result, o_result_format, o_result_signed, o_predicate_valid, o_predicate,
        o_carry, o_borrow, o_overflow, o_saturated, o_zero, o_negative};
    vector_lane_reference #(.E(ELEMENT_WIDTH), .A(A), .MUL(SUPPORT_MUL), .MAC(SUPPORT_MAC),
        .SAT(SUPPORT_SATURATION), .MINMAX(SUPPORT_MINMAX)) reference_unit (
        .response(reference_now), .*);
    if (L == 0) begin : g_direct
        always_comb assert (actual == reference_now);
    end else begin : g_history
        logic [A+14:0] history[L];
        bit initialized = 1'b0;
        always @(posedge i_clk) begin
            if (!i_rstb) begin
                initialized <= 1'b1;
                for (int k = 0; k < L; k++) history[k] <= '0;
            end else if (i_clock_enable) begin
                history[0] <= reference_now;
                for (int k = 1; k < L; k++) history[k] <= history[k-1];
            end
        end
        // Async-to-sync clock abstraction is used only for sampled-edge proofs;
        // clockless assertion/release behavior is separately checked in PyUVM.
        always_comb assert (!initialized || !i_rstb || actual == history[L-1]);
    end
endmodule
