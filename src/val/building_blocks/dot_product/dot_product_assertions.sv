`timescale 1ns / 1ps

// Verification-only oracle: a serial, over-wide mathematical sum and an
// enabled-edge response history. It never reads DUT products or reduction nodes.
module dot_product_assertions #(
    parameter int E = 8,
    parameter int N = 4,
    parameter int A = 32,
    parameter int L = 2,
    parameter int ASYNC_RESET = 0,
    parameter int SUPPORT_ACCUMULATE = 1,
    parameter int SUPPORT_SATURATION = 1,
    localparam int C = $clog2(N + 1),
    localparam int B = A + C + 7,
    localparam int REF_WIDTH = A + 2 * E + $clog2(N) + 2
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [N-1:0] i_term_mask,
    input logic [N*E-1:0] i_operand_a,
    input logic [N*E-1:0] i_operand_b,
    input logic i_accumulate,
    input logic [A-1:0] i_accumulator,
    input logic i_signed,
    input logic i_saturate,
    input logic o_valid,
    input logic [A-1:0] o_result,
    input logic [C-1:0] o_active_count,
    input logic o_carry,
    input logic o_overflow,
    input logic o_saturated,
    input logic o_zero,
    input logic o_negative,
    input logic o_illegal_operation
);
    wire [B-1:0] actual = {
        o_valid,
        o_illegal_operation,
        o_result,
        o_active_count,
        o_carry,
        o_overflow,
        o_saturated,
        o_zero,
        o_negative
    };

    function automatic logic [B-1:0] reference_response(
        input logic valid, input logic [N-1:0] mask, input logic [N*E-1:0] operand_a,
        input logic [N*E-1:0] operand_b, input logic accumulate, input logic [A-1:0] accumulator,
        input logic signed_mode, input logic saturate);
        logic signed [REF_WIDTH-1:0] total;
        logic signed [REF_WIDTH-1:0] left;
        logic signed [REF_WIDTH-1:0] right;
        logic signed [REF_WIDTH-1:0] low;
        logic signed [REF_WIDTH-1:0] high;
        logic [A-1:0] result;
        logic [A-1:0] wrapped;
        logic [C-1:0] count;
        logic carry;
        logic overflow;
        logic saturated;
        if (valid !== 1'b1) return '0;
        if (( ^ {mask, accumulate, signed_mode, saturate} === 1'bx) ||
            (accumulate && SUPPORT_ACCUMULATE == 0) ||
            (saturate && SUPPORT_SATURATION == 0))
            return {2'b11, {(B - 2) {1'b0}}};
        total = '0;
        count = '0;
        for (int k = 0; k < N; k ++ ) begin
            if (mask[k]) begin
                left = signed_mode ? REF_WIDTH'($signed(operand_a[k*E+:E])) :
                    REF_WIDTH'(operand_a[k*E+:E]);
                right = signed_mode ? REF_WIDTH'($signed(operand_b[k*E+:E])) :
                    REF_WIDTH'(operand_b[k*E+:E]);
                total = total + left * right;
                count = count + 1'b1;
            end
        end
        if (accumulate) begin
            left = signed_mode ? REF_WIDTH'($signed(accumulator)) : REF_WIDTH'(accumulator);
            total = total + left;
        end
        low = signed_mode ? - (REF_WIDTH'(1) << (A - 1)) : REF_WIDTH'(0);
        high = signed_mode ? (REF_WIDTH'(1) << (A - 1)) - 1 : (REF_WIDTH'(1) << A) - 1;
        wrapped = total[A-1:0];
        result = wrapped;
        if (saturate && total < low) result = low[A-1:0];
        if (saturate && total > high) result = high[A-1:0];
        carry = accumulate &&!signed_mode && total > high;
        overflow = accumulate && signed_mode && (total < low || total > high);
        saturated = result != wrapped;
        return {
            1'b1,
            1'b0,
            result,
            count,
            carry,
            overflow,
            saturated,
            result == 0,
            signed_mode && result[A-1]
        };
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
            if (i_valid === 1'b1 &&
                ( ^ {i_term_mask, i_accumulate, i_signed, i_saturate} !== 1'bx) &&
                (!i_accumulate || SUPPORT_ACCUMULATE == 1) &&
                (!i_saturate || SUPPORT_SATURATION == 1)) begin
                for (int k = 0; k < N; k ++ ) begin
                    if (i_term_mask[k]) begin
                        assert ( ^ i_operand_a[k*E+:E] !== 1'bx)
                        else $fatal(1, "Protocol assertion failed: i_operand_a");
                        assert ( ^ i_operand_b[k*E+:E] !== 1'bx)
                        else $fatal(1, "Protocol assertion failed: i_operand_b");
                    end
                end
                if (i_accumulate) begin
                    assert ( ^ i_accumulator !== 1'bx)
                    else $fatal(1, "Protocol assertion failed: i_accumulator");
                end
            end
        end
    endtask

    if (L == 0) begin : g_combinational
        always @( * ) begin
            #1ps;
            check_protocol();
            assert (actual === reference_response(
                i_valid,
                i_term_mask,
                i_operand_a,
                i_operand_b,
                i_accumulate,
                i_accumulator,
                i_signed,
                i_saturate
            ))
            else $fatal(1, "DOT_PRODUCT_HDL: combinational arithmetic/status");
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
                    i_valid,
                    i_term_mask,
                    i_operand_a,
                    i_operand_b,
                    i_accumulate,
                    i_accumulator,
                    i_signed,
                    i_saturate
                );
            end
            #1ps;
            if (initialized) begin
                assert (actual === expected[L-1])
                else $fatal(1, "DOT_PRODUCT_HDL: enabled latency/arithmetic/status/reset");
            end
        endtask
        if (ASYNC_RESET == 1) begin : g_async
            always @(posedge i_clk or negedge i_rstb) check_edge();
        end else begin : g_sync
            always @(posedge i_clk) check_edge();
        end
    end
endmodule
