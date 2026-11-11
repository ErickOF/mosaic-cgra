`timescale 1ns / 1ps

// Scalar MAC specialization of the exact dot-product datapath. With one term,
// the reduction tree is a wire; accumulation is always enabled. The reused core
// owns product extension, saturation, operand isolation and enabled-edge timing.
module mac #(
    parameter OPERAND_WIDTH = 8,
    parameter ACC_WIDTH = 32,
    parameter SUPPORT_SATURATION = 1,
    parameter LATENCY = 1,
    parameter MAX_LATENCY = 4,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((OPERAND_WIDTH >= 1) === 1'b1) && (((^OPERAND_WIDTH == 1'b0) || (^OPERAND_WIDTH == 1'b1)) === 1'b1) &&
        ((ACC_WIDTH >= 1) === 1'b1) && (((^ACC_WIDTH == 1'b0) || (^ACC_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(ACC_WIDTH) >= 2 * 64'(OPERAND_WIDTH)) === 1'b1) &&
        ((MAX_LATENCY >= 1) === 1'b1) && (((^MAX_LATENCY == 1'b0) || (^MAX_LATENCY == 1'b1)) === 1'b1) &&
        ((LATENCY >= 0) === 1'b1) && ((LATENCY <= MAX_LATENCY) === 1'b1) &&
        (((^LATENCY == 1'b0) || (^LATENCY == 1'b1)) === 1'b1) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((64'(ACC_WIDTH) * (64'(LATENCY) + 1) < 64'd2147483647) === 1'b1),
    localparam int W = PARAMETERS_VALID ? OPERAND_WIDTH : 1,
    localparam int PRODUCT_WIDTH = 2 * W,
    localparam int A = PARAMETERS_VALID ? ACC_WIDTH : PRODUCT_WIDTH
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [W-1:0] i_operand_a,
    input logic [W-1:0] i_operand_b,
    input logic [A-1:0] i_accumulator,
    input logic i_signed,
    input logic i_saturate,
    output logic o_valid,
    output logic [A-1:0] o_result,
    output logic o_carry,
    output logic o_overflow,
    output logic o_saturated,
    output logic o_zero,
    output logic o_negative,
    output logic o_illegal_operation
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        mac_parameters_must_be_valid invalid_parameters ();
    end else begin : g_mac
        // The count has no architectural meaning for a scalar operation. Keep
        // its connection for the shared verification checker; synthesis removes it.
        wire unused_active_count;

        dot_product #(
            .ELEMENT_WIDTH(W),
            .NUM_TERMS(1),
            .ACC_WIDTH(A),
            .SUPPORT_ACCUMULATE(1),
            .SUPPORT_SATURATION(SUPPORT_SATURATION),
            .LATENCY(LATENCY),
            .MAX_LATENCY(MAX_LATENCY),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_core (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(i_clock_enable),
            .i_valid(i_valid),
            .i_term_mask(1'b1),
            .i_operand_a(i_operand_a),
            .i_operand_b(i_operand_b),
            .i_accumulate(1'b1),
            .i_accumulator(i_accumulator),
            .i_signed(i_signed),
            .i_saturate(i_saturate),
            .o_valid(o_valid),
            .o_result(o_result),
            .o_active_count(unused_active_count),
            .o_carry(o_carry),
            .o_overflow(o_overflow),
            .o_saturated(o_saturated),
            .o_zero(o_zero),
            .o_negative(o_negative),
            .o_illegal_operation(o_illegal_operation)
        );

`ifdef MOSAIC_MAC_ASSERTIONS
        // Verification only: independent wide-integer arithmetic and enabled-edge
        // history. Unknown active data/valid/clock/reset are rejected here, before
        // integration may commit a result. X/Z arithmetic modes return illegal.
        dot_product_assertions #(
            .E(W),
            .N(1),
            .A(A),
            .L(LATENCY),
            .ASYNC_RESET(ASYNC_RESET),
            .SUPPORT_ACCUMULATE(1),
            .SUPPORT_SATURATION(SUPPORT_SATURATION)
        ) u_assertions (
            .i_term_mask(1'b1),
            .i_accumulate(1'b1),
            .o_active_count(unused_active_count),
            .*
        );
`endif
    end
endmodule
