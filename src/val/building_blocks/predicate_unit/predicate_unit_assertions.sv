`timescale 1ns / 1ps

// Native four-state assertions compare pre-edge evaluation with post-edge state.
// Delays are verification-only; this module is excluded from synthesis and gates.
module predicate_unit_assertions #(
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

    task automatic check_edge;
        assert (i_rstb === 1'b0 || i_rstb === 1'b1)
        else $fatal(1, "PREDICATE_UNIT_PROTOCOL: i_rstb");
        if (i_rstb === 1'b1) begin
            assert (i_clock_enable === 1'b0 || i_clock_enable === 1'b1)
            else $fatal(1, "PREDICATE_UNIT_PROTOCOL: i_clock_enable");
            if (i_clock_enable === 1'b1) begin
                assert (i_valid === 1'b0 || i_valid === 1'b1)
                else $fatal(1, "PREDICATE_UNIT_PROTOCOL: i_valid");
                if (i_valid === 1'b1 && legal && i_opcode == 2) begin
                    for (int lane = 0; lane < N; lane++) begin
                        if (i_lane_mask[lane]) begin
                            assert (i_predicate_input[lane] === 1'b0 ||
                                i_predicate_input[lane] === 1'b1)
                            else $fatal(1, "PREDICATE_UNIT_PROTOCOL: load%0d", lane);
                        end
                    end
                end
            end
        end else initialized = 1'b1;
        #1ps;
        if (initialized) begin
            assert (actual === response)
            else $fatal(1, "PREDICATE_UNIT_HDL: response actual=%h expected=%h", actual, response);
            for (int entry = 0; entry < D; entry++) begin
                assert (actual_valid[entry*N+:N] === validity[entry*N+:N])
                else $fatal(1, "PREDICATE_UNIT_HDL: validity entry %0d", entry);
                // Only initialized payload bits are compared by the Python
                // model; this native comparison additionally tracks stale bits.
                assert (actual_data[entry*N+:N] === data[entry*N+:N])
                else $fatal(1, "PREDICATE_UNIT_HDL: data entry %0d", entry);
            end
        end
    endtask

    if (ASYNC_RESET == 1) begin : g_async
        always @(posedge i_clk or negedge i_rstb) check_edge();
    end else begin : g_sync
        always @(posedge i_clk) check_edge();
    end
endmodule
