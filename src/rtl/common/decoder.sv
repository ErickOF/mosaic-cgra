`timescale 1ns / 1ps

/// Parameterizable binary-to-one-hot decoder with fail-closed invalid handling.
module decoder #(
    parameter int unsigned NUM_OUTPUTS  = 4,
    parameter int unsigned SELECT_WIDTH = (NUM_OUTPUTS > 1) ? $clog2(NUM_OUTPUTS) : 1
) (
    input  logic                    i_enable,
    input  logic [SELECT_WIDTH-1:0] i_select,
    output logic [ NUM_OUTPUTS-1:0] o_decoded,
    output logic                    o_select_valid
);

    localparam int unsigned ExpectedSelectWidth = (NUM_OUTPUTS > 1) ? $clog2(NUM_OUTPUTS) : 1;

    generate
        if (NUM_OUTPUTS < 1) begin : g_invalid_num_outputs
            decoder_num_outputs_must_be_greater_than_zero invalid_num_outputs ();
        end
        if (SELECT_WIDTH != ExpectedSelectWidth) begin : g_invalid_select_width
            decoder_select_width_must_match_num_outputs invalid_select_width ();
        end
    endgenerate

    always_comb begin
        o_decoded = '0;
        o_select_valid = 1'b0;

        // A four-state condition executes only when enable and selection are
        // both known and legal. Unknown controls therefore fail closed.
        if (i_enable && ({1'b0, i_select} < (SELECT_WIDTH + 1)'(NUM_OUTPUTS))) begin
            o_decoded[i_select] = 1'b1;
            o_select_valid = 1'b1;
        end
    end

endmodule
