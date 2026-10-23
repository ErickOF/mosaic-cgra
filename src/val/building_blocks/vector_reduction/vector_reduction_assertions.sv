`timescale 1ns / 1ps

// Native four-state checks and whole-response history complement PyUVM's
// integer oracle, deadline ledger and passive checks of the real DFF pins.
module vector_reduction_assertions #(
    parameter int E = 8,
    parameter int N = 4,
    parameter int A = 32,
    parameter int L = 1,
    parameter int ASYNC_RESET = 0,
    parameter int SUM = 1,
    parameter int MINMAX = 1,
    parameter int LOGICAL = 1,
    localparam int C = $clog2(N + 1),
    localparam int B = A + C + 7
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [2:0] i_opcode,
    input logic [N-1:0] i_element_mask,
    input logic [N*E-1:0] i_data,
    input logic i_signed,
    input logic o_valid,
    input logic [A-1:0] o_result,
    input logic [1:0] o_result_format,
    input logic o_result_signed,
    input logic [C-1:0] o_active_count,
    input logic o_zero,
    input logic o_negative,
    input logic o_illegal_operation
);
    wire [B-1:0] reference_now;
    wire [B-1:0] actual = {o_valid, o_result, o_result_format, o_result_signed,
        o_active_count, o_zero, o_negative, o_illegal_operation};
    vector_reduction_reference #(.E(E), .N(N), .A(A), .SUM(SUM), .MINMAX(MINMAX),
        .LOGICAL(LOGICAL)) u_reference (.response(reference_now), .*);

    task automatic check_protocol;
        if (L > 0) begin
            assert (i_rstb === 1'b0 || i_rstb === 1'b1)
            else $fatal(1, "VECTOR_REDUCTION_PROTOCOL: i_rstb");
            if (i_rstb === 1'b1) begin
                assert (i_clock_enable === 1'b0 || i_clock_enable === 1'b1)
                else $fatal(1, "VECTOR_REDUCTION_PROTOCOL: i_clock_enable");
            end
        end
        if (L == 0 || (i_rstb === 1'b1 && i_clock_enable === 1'b1)) begin
            assert (i_valid === 1'b0 || i_valid === 1'b1)
            else $fatal(1, "VECTOR_REDUCTION_PROTOCOL: i_valid");
            if (i_valid === 1'b1 && reference_now[0] === 1'b0) begin
                for (int k = 0; k < N; k++) begin
                    if (i_element_mask[k]) begin
                        assert ( ^ i_data[k*E+:E] !== 1'bx)
                        else $fatal(1, "VECTOR_REDUCTION_PROTOCOL: element %0d", k);
                    end
                end
            end
        end
    endtask

    if (L == 0) begin : g_combinational
        // Include request data explicitly: active X/Z must be rejected even
        // when an AND-zero/OR-ones operand keeps both result oracles unchanged.
        always @(i_valid or i_opcode or i_element_mask or i_data or i_signed or
            actual or reference_now) begin
            #1ps;
            check_protocol();
            assert (actual === reference_now)
            else $fatal(1, "VECTOR_REDUCTION_HDL: combinational arithmetic/format/status");
        end
    end else begin : g_pipeline
        logic [B-1:0] expected[L];
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
                assert (actual === expected[L-1])
                else $fatal(1, "VECTOR_REDUCTION_HDL: actual=%h expected=%h opcode=%d",
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
