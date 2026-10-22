`timescale 1ns / 1ps

// Verification-only mathematical reference: convert each bit pattern using a
// subtractive two's-complement interpretation in a wider signed domain. No DUT
// intermediate, operand-extension cast, or pipeline register feeds this oracle.
module multiplier_assertions #(
    parameter int W = 32,
    parameter int L = 1,
    parameter int ASYNC_RESET = 0,
    localparam int P = 2 * W,
    localparam int B = P + 4,
    localparam int R = P + 2
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [W-1:0] i_operand_a,
    input logic [W-1:0] i_operand_b,
    input logic i_signed_a,
    input logic i_signed_b,
    input logic o_valid,
    input logic [P-1:0] o_product,
    input logic o_product_signed,
    input logic o_zero,
    input logic o_negative
);
    wire [B-1:0] actual = {o_valid, o_product, o_product_signed, o_zero, o_negative};

    function automatic logic [B-1:0] reference_response(
        input logic valid,
        input logic [W-1:0] a,
        input logic [W-1:0] b,
        input logic signed_a,
        input logic signed_b
    );
        logic signed [R-1:0] left;
        logic signed [R-1:0] right;
        logic signed [R-1:0] product;
        logic product_signed;
        if (valid !== 1'b1) return '0;
        left = R'(a);
        right = R'(b);
        if (signed_a && a[W-1]) left = left - (R'(1) << W);
        if (signed_b && b[W-1]) right = right - (R'(1) << W);
        product = left * right;
        product_signed = signed_a || signed_b;
        return {1'b1, product[P-1:0], product_signed, product == 0, product < 0};
    endfunction

    task automatic check_protocol;
        if (L > 0) begin
            assert (i_rstb === 1'b0 || i_rstb === 1'b1)
            else $fatal(1, "Protocol assertion failed: i_rstb");
            if (i_rstb === 1'b1) begin
                assert (i_clock_enable === 1'b0 || i_clock_enable === 1'b1)
                else $fatal(1, "Protocol assertion failed: i_clock_enable");
            end
        end
        if (L == 0 || (i_rstb === 1'b1 && i_clock_enable === 1'b1)) begin
            assert (i_valid === 1'b0 || i_valid === 1'b1)
            else $fatal(1, "Protocol assertion failed: i_valid");
            if (i_valid === 1'b1) begin
                assert ( ^ i_signed_a !== 1'bx)
                else $fatal(1, "Protocol assertion failed: i_signed_a");
                assert ( ^ i_signed_b !== 1'bx)
                else $fatal(1, "Protocol assertion failed: i_signed_b");
                assert ( ^ i_operand_a !== 1'bx)
                else $fatal(1, "Protocol assertion failed: i_operand_a");
                assert ( ^ i_operand_b !== 1'bx)
                else $fatal(1, "Protocol assertion failed: i_operand_b");
            end
        end
    endtask

    if (L == 0) begin : g_combinational
        always @(*) begin
            #1ps;
            check_protocol();
            assert (actual === reference_response(
                i_valid, i_operand_a, i_operand_b, i_signed_a, i_signed_b
            ))
            else $fatal(1, "MULTIPLIER_HDL: combinational arithmetic/status");
        end
    end else begin : g_pipeline
        logic [B-1:0] expected[L];
        bit initialized = 1'b0;

        task automatic check_edge;
            check_protocol();
            if (!i_rstb) begin
                for (int k = 0; k < L; k ++ ) expected[k] = '0;
                initialized = 1'b1;
            end else if (i_clock_enable) begin
                for (int k = L - 1; k > 0; k -- ) expected[k] = expected[k-1];
                expected[0] = reference_response(
                    i_valid, i_operand_a, i_operand_b, i_signed_a, i_signed_b
                );
            end
            #1ps;
            if (initialized) begin
                assert (actual === expected[L-1])
                else $fatal(1, "MULTIPLIER_HDL: enabled latency/arithmetic/status/reset");
            end
        endtask

        if (ASYNC_RESET == 1) begin : g_async
            always @(posedge i_clk or negedge i_rstb) check_edge();
        end else begin : g_sync
            always @(posedge i_clk) check_edge();
        end
    end
endmodule
