`timescale 1ns / 1ps

// Atomic, zero-storage join. Producers hold early operands and the integration
// holds the required mask until the complete operation is accepted.
module stream_join #(
    parameter NUM_INPUTS = 2,
    parameter DATA_WIDTH = 32,
    parameter HAS_REQUIRED_MASK = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_INPUTS >= 1) === 1'b1) &&
        ((DATA_WIDTH >= 1) === 1'b1) &&
        ((HAS_REQUIRED_MASK === 0) || (HAS_REQUIRED_MASK === 1)),
    localparam int unsigned INPUTS = PARAMETERS_VALID ? NUM_INPUTS : 1,
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned OUTPUT_WIDTH = INPUTS * DATA_BITS
) (
    input  logic [INPUTS-1:0]       i_valid,
    output logic [INPUTS-1:0]       o_ready,
    input  logic [OUTPUT_WIDTH-1:0] i_data,
    input  logic [INPUTS-1:0]       i_required,
    output logic                    o_valid,
    input  logic                    i_ready,
    output logic [OUTPUT_WIDTH-1:0] o_data,
    output logic [INPUTS-1:0]       o_required
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        stream_join_parameters_must_be_valid invalid_parameters ();
    end else begin : g_join
        wire [INPUTS-1:0] required;
        wire [INPUTS-1:0] qualified = ~required | i_valid;

        if (HAS_REQUIRED_MASK == 1) begin : g_runtime_mask
            assign required = i_required;
        end else begin : g_all_inputs
            wire unused_required = ^i_required;
            assign required = '1;
        end

        // Exclusive prefix/suffix terms omit each lane's own valid. Unlike
        // gating every ready with o_valid, this exposes ready to a final missing
        // producer. Bitwise logic preserves uncertainty in required controls.
        assign o_valid = (|required) & (&qualified);
        for (genvar k = 0; k < INPUTS; k++) begin : g_input
            wire prefix;
            wire suffix;
            if (k == 0) begin : g_first
                assign prefix = 1'b1;
            end else begin : g_prefix
                assign prefix = g_input[k-1].prefix & qualified[k-1];
            end
            if (k == INPUTS-1) begin : g_last
                assign suffix = 1'b1;
            end else begin : g_suffix
                assign suffix = g_input[k+1].suffix & qualified[k+1];
            end
            assign o_ready[k] = required[k] & i_ready & prefix & suffix;

            operand_isolation #(.WIDTH(DATA_BITS)) u_invalid_output (
                .i_data(i_data[k * DATA_BITS +: DATA_BITS]),
                .i_isolate(!(o_valid & required[k])),
                .o_data(o_data[k * DATA_BITS +: DATA_BITS])
            );
        end

        operand_isolation #(.WIDTH(INPUTS)) u_invalid_mask (
            .i_data(required),
            .i_isolate(!o_valid),
            .o_data(o_required)
        );
    end
endmodule
