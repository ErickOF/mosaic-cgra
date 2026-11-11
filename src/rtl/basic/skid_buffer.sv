`timescale 1ns / 1ps

// One late-stall storage entry. Forward traffic bypasses while empty; upstream
// ready depends only on registered state. Payload/reset policy belongs to users.
module skid_buffer #(
    parameter DATA_WIDTH = 32,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1) === 1'b1) && (((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1
) (
    input  logic                 i_clk,
    input  logic                 i_rstb,
    input  logic                 i_valid,
    output logic                 o_ready,
    input  logic [DATA_BITS-1:0] i_data,
    output logic                 o_valid,
    input  logic                 i_ready,
    output logic [DATA_BITS-1:0] o_data
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        skid_buffer_parameters_must_be_valid invalid_parameters ();
    end else begin : g_skid
        logic buffer_valid;
        logic [DATA_BITS-1:0] buffer_data;
        wire capture = !buffer_valid && i_valid && !i_ready;
        wire release_buffer = buffer_valid && i_ready;
        wire data_enable = i_rstb && capture;
        wire [DATA_BITS-1:0] selected_data;
        wire unused_select_valid;

        assign o_ready = !buffer_valid;
        assign o_valid = buffer_valid || i_valid;

        // Reset changes occupancy only. In particular, reset does not mask a
        // valid producer's bypass; the integration must suppress reset traffic.
        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(capture || release_buffer),
            .i_d(capture),
            .o_q(buffer_valid)
        );

        // Bypass, idle, hold, release and reset preserve the unreset payload.
        // A full entry cannot accept a replacement on its release edge.
        always_ff @(posedge i_clk) begin
            if (data_enable) buffer_data <= i_data;
        end

        mux #(.NUM_INPUTS(2), .DATA_WIDTH(DATA_BITS)) u_output_select (
            .i_data({buffer_data, i_data}),
            .i_select(buffer_valid),
            .o_data(selected_data),
            .o_select_valid(unused_select_valid)
        );
        operand_isolation #(.WIDTH(DATA_BITS)) u_invalid_output (
            .i_data(selected_data),
            .i_isolate(!o_valid),
            .o_data(o_data)
        );
    end
endmodule
