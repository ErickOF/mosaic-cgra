`timescale 1ns / 1ps

// One stored multicast item. Each pending destination consumes independently;
// the last consumption may coincide with acceptance of the following item.
module stream_fork #(
    parameter NUM_OUTPUTS = 2,
    parameter DATA_WIDTH = 32,
    parameter HAS_DESTINATION_MASK = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_OUTPUTS >= 1) === 1'b1) && (((^NUM_OUTPUTS == 1'b0) || (^NUM_OUTPUTS == 1'b1)) === 1'b1) &&
        ((DATA_WIDTH >= 1) === 1'b1) && (((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((HAS_DESTINATION_MASK === 0) || (HAS_DESTINATION_MASK === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    localparam int unsigned OUTPUTS = PARAMETERS_VALID ? NUM_OUTPUTS : 1,
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned OUTPUT_WIDTH = OUTPUTS * DATA_BITS
) (
    input  logic                    i_clk,
    input  logic                    i_rstb,
    input  logic                    i_valid,
    output logic                    o_ready,
    input  logic [DATA_BITS-1:0]    i_data,
    input  logic [OUTPUTS-1:0]      i_destination,
    output logic [OUTPUTS-1:0]      o_valid,
    input  logic [OUTPUTS-1:0]      i_ready,
    output logic [OUTPUT_WIDTH-1:0] o_data
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        stream_fork_parameters_must_be_valid invalid_parameters ();
    end else begin : g_fork
        logic [DATA_BITS-1:0] fork_data;
        logic [OUTPUTS-1:0] pending;
        wire [OUTPUTS-1:0] remaining = pending & ~i_ready;
        wire input_accept = i_valid && o_ready;
        wire data_enable = i_rstb && input_accept;
        wire [OUTPUTS-1:0] destination;

        // A completed/unselected output cannot backpressure the active item,
        // even when its ready is X/Z. No input payload/control bypass exists.
        assign o_ready = ~(|remaining);
        assign o_valid = pending;
        if (HAS_DESTINATION_MASK == 1) begin : g_runtime_mask
            assign destination = i_destination;
        end else begin : g_all_outputs
            wire unused_destination = ^i_destination;
            assign destination = '1;
        end

        // Common DFF selects reset style statically. The enable suppresses
        // pending-state writes during idle and stalls without generating clocks.
        dff #(.WIDTH(OUTPUTS), .ASYNC_RESET(ASYNC_RESET != 0)) u_pending (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(input_accept || (|(pending & i_ready))),
            .i_d(input_accept ? destination : remaining),
            .o_q(pending)
        );

        // Payload has no reset: validity masks arbitrary initial/stale data.
        // Reset edges must neither accept inputs nor overwrite stored payload.
        always_ff @(posedge i_clk) begin
            if (data_enable) fork_data <= i_data;
        end

        for (genvar k = 0; k < OUTPUTS; k++) begin : g_output
            operand_isolation #(.WIDTH(DATA_BITS)) u_invalid_output (
                .i_data(fork_data),
                .i_isolate(!pending[k]),
                .o_data(o_data[k * DATA_BITS +: DATA_BITS])
            );
        end
    end
endmodule
