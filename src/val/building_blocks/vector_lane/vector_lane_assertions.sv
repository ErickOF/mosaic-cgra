`timescale 1ns / 1ps

// Native integration checks complement the independent Python deadline ledger.
// This checker is excluded from synthesized/gate-level sources by the Makefile.
module vector_lane_assertions #(
    parameter int E = 8,
    parameter int A = 32,
    parameter int L = 1,
    parameter int ASYNC_RESET = 0,
    parameter int MUL = 1,
    parameter int MAC = 1,
    parameter int SAT = 1,
    parameter int MINMAX = 1
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
    input logic [E-1:0] i_operand_a,
    input logic [E-1:0] i_operand_b,
    input logic [A-1:0] i_accumulator,
    input logic i_signed,
    input logic i_saturate,
    input logic o_valid,
    input logic o_write_enable,
    input logic o_suppressed,
    input logic o_illegal_operation,
    input logic [A-1:0] o_result,
    input logic [1:0] o_result_format,
    input logic o_result_signed,
    input logic o_predicate_valid,
    input logic o_predicate,
    input logic o_carry,
    input logic o_borrow,
    input logic o_overflow,
    input logic o_saturated,
    input logic o_zero,
    input logic o_negative,
    input logic [2:0] i_path_valid
);
    wire [A+14:0] reference_now;
    wire [A+14:0] actual = {o_valid, o_write_enable, o_suppressed, o_illegal_operation,
        o_result, o_result_format, o_result_signed, o_predicate_valid, o_predicate,
        o_carry, o_borrow, o_overflow, o_saturated, o_zero, o_negative};
    vector_lane_reference #(.E(E), .A(A), .MUL(MUL), .MAC(MAC), .SAT(SAT),
        .MINMAX(MINMAX)) u_reference (.response(reference_now), .*);

    task automatic check_protocol;
        if (L > 0) begin
            assert (i_rstb === 1'b0 || i_rstb === 1'b1)
            else $fatal(1, "VECTOR_LANE_PROTOCOL: i_rstb");
            if (i_rstb === 1'b1) begin
                assert (i_clock_enable === 1'b0 || i_clock_enable === 1'b1)
                else $fatal(1, "VECTOR_LANE_PROTOCOL: i_clock_enable");
            end
        end
        if (L == 0 || (i_rstb === 1'b1 && i_clock_enable === 1'b1)) begin
            assert (i_valid === 1'b0 || i_valid === 1'b1)
            else $fatal(1, "VECTOR_LANE_PROTOCOL: i_valid");
            if (reference_now[A+13] === 1'b1) begin
                if (i_opcode != 17 && (i_opcode != 15 || i_select_predicate)) begin
                    assert ( ^ i_operand_a !== 1'bx)
                    else $fatal(1, "VECTOR_LANE_PROTOCOL: i_operand_a");
                end
                if (i_opcode != 5 && i_opcode != 16 &&
                    (i_opcode != 15 || !i_select_predicate)) begin
                    assert ( ^ i_operand_b !== 1'bx)
                    else $fatal(1, "VECTOR_LANE_PROTOCOL: i_operand_b");
                end
                if (i_opcode == 21) begin
                    assert ( ^ i_accumulator !== 1'bx)
                    else $fatal(1, "VECTOR_LANE_PROTOCOL: i_accumulator");
                end
            end
        end
    endtask

    task automatic check_paths;
        if (o_write_enable) begin
            assert (i_path_valid == 3'b001 || i_path_valid == 3'b010 || i_path_valid == 3'b100)
            else $fatal(1, "VECTOR_LANE_HDL: exactly one aligned functional unit");
        end
    endtask

    if (L == 0) begin : g_combinational
        always @(*) begin
            #1ps;
            check_protocol();
            check_paths();
            assert (actual === reference_now)
            else $fatal(1, "VECTOR_LANE_HDL: combinational arithmetic/format/status");
        end
    end else begin : g_pipeline
        logic [A+14:0] expected[L];
        bit initialized = 1'b0;
        task automatic check_edge;
            check_protocol();
            if (!i_rstb) begin
                for (int k = 0; k < L; k++) expected[k] = '0;
                initialized = 1'b1;
            end else if (i_clock_enable) begin
                for (int k = L - 1; k > 0; k--) expected[k] = expected[k-1];
                expected[0] = reference_now;
            end
            #1ps;
            if (initialized) begin
                check_paths();
                assert (actual === expected[L-1])
                else $fatal(1, "VECTOR_LANE_HDL: actual=%h expected=%h opcode=%d",
                    actual, expected[L-1], i_opcode);
            end
        endtask
        if (ASYNC_RESET == 1) begin : g_async
            always @(posedge i_clk or negedge i_rstb) check_edge();
        end else begin : g_sync
            always @(posedge i_clk) check_edge();
        end
    end
endmodule
