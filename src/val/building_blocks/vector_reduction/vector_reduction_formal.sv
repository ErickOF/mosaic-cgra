`timescale 1ns / 1ps

// Two-state mathematical equivalence and enabled-edge bounded response history.
// Async assertions between sampled clocks are checked separately in simulation.
module vector_reduction_formal #(
    parameter ELEMENT_WIDTH = 8,
    parameter NUM_ELEMENTS = 4,
    parameter ACC_WIDTH = 32,
    parameter SUPPORT_SUM = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter SUPPORT_LOGICAL = 1,
    parameter LATENCY = 1,
    parameter MAX_LATENCY = 8,
    parameter ASYNC_RESET = 0,
    parameter OPCODE_WIDTH = 3,
    parameter RESULT_FORMAT_WIDTH = 2
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [2:0] i_opcode,
    input logic [NUM_ELEMENTS-1:0] i_element_mask,
    input logic [NUM_ELEMENTS*ELEMENT_WIDTH-1:0] i_data,
    input logic i_signed,
    output wire o_valid,
    output wire [ACC_WIDTH-1:0] o_result,
    output wire [1:0] o_result_format,
    output wire o_result_signed,
    output wire [$clog2(NUM_ELEMENTS+1)-1:0] o_active_count,
    output wire o_zero,
    output wire o_negative,
    output wire o_illegal_operation
);
    localparam int A = ACC_WIDTH;
    localparam int C = $clog2(NUM_ELEMENTS + 1);
    localparam int B = A + C + 7;
    localparam int L = LATENCY;
    vector_reduction #(
        .ELEMENT_WIDTH(ELEMENT_WIDTH),
        .NUM_ELEMENTS(NUM_ELEMENTS),
        .ACC_WIDTH(ACC_WIDTH),
        .SUPPORT_SUM(SUPPORT_SUM),
        .SUPPORT_MINMAX(SUPPORT_MINMAX),
        .SUPPORT_LOGICAL(SUPPORT_LOGICAL),
        .LATENCY(LATENCY),
        .MAX_LATENCY(MAX_LATENCY),
        .ASYNC_RESET(ASYNC_RESET),
        .OPCODE_WIDTH(OPCODE_WIDTH),
        .RESULT_FORMAT_WIDTH(RESULT_FORMAT_WIDTH)
    ) dut (.*);
    wire [B-1:0] reference_now;
    wire [B-1:0] actual = {o_valid, o_result, o_result_format, o_result_signed,
        o_active_count, o_zero, o_negative, o_illegal_operation};
    vector_reduction_reference #(.E(ELEMENT_WIDTH), .N(NUM_ELEMENTS), .A(A),
        .SUM(SUPPORT_SUM), .MINMAX(SUPPORT_MINMAX), .LOGICAL(SUPPORT_LOGICAL)) reference_unit (
        .response(reference_now), .*);
    if (L == 0) begin : g_direct
        always_comb assert (actual == reference_now);
    end else begin : g_history
        logic [B-1:0] history[L];
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
        always_comb assert (!initialized || !i_rstb || actual == history[L-1]);
        if (ASYNC_RESET == 1) begin : g_reset_clamp
            always_comb assert (i_rstb || actual == 0);
        end
    end
endmodule
