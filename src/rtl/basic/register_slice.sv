`timescale 1ns / 1ps

// One elastic forward pipeline boundary. The reverse ready path is combinational;
// reset sequencing, item interpretation and producer stability belong to users.
module register_slice #(
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
        register_slice_parameters_must_be_valid invalid_parameters ();
    end else begin : g_slice
        logic slice_valid;
        logic [DATA_BITS-1:0] slice_data;
        wire load_enable = !slice_valid || i_ready;
        wire data_enable = i_rstb && load_enable && i_valid;

        assign o_ready = load_enable;
        assign o_valid = slice_valid;
        // No reset-dependent output clamp: synchronous reset takes effect at
        // its edge, while the asynchronous DFF clears validity immediately.
        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(load_enable),
            .i_d(i_valid),
            .o_q(slice_valid)
        );

        // Only an accepted valid input writes payload. Bubbles, backpressure
        // and reset preserve it; consumption reads the old value before NBA.
        always_ff @(posedge i_clk) begin
            if (data_enable) slice_data <= i_data;
        end

        operand_isolation #(.WIDTH(DATA_BITS)) u_invalid_output (
            .i_data(slice_data),
            .i_isolate(!slice_valid),
            .o_data(o_data)
        );
    end
endmodule
