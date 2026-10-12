`timescale 1ns / 1ps

/// Parameterizable N-to-1 multiplexer with fail-closed invalid handling.
module mux #(
    parameter int unsigned NUM_INPUTS = 2,
    parameter int unsigned DATA_WIDTH = 32,
    parameter logic [DATA_WIDTH-1:0] DEFAULT_VALUE = '0,
    parameter int unsigned SEL_WIDTH = (NUM_INPUTS > 1) ? $clog2(NUM_INPUTS) : 1
) (
    input  logic [NUM_INPUTS-1:0][DATA_WIDTH-1:0] i_data,
    input  logic [ SEL_WIDTH-1:0]                 i_select,
    output logic [DATA_WIDTH-1:0]                 o_data,
    output logic                                  o_select_valid
);

    localparam int unsigned ExpectedSelWidth = (NUM_INPUTS > 1) ? $clog2(NUM_INPUTS) : 1;

    generate
        if (NUM_INPUTS < 1) begin : g_invalid_num_inputs
            mux_num_inputs_must_be_greater_than_zero invalid_num_inputs ();
        end
        if (DATA_WIDTH < 1) begin : g_invalid_data_width
            mux_data_width_must_be_greater_than_zero invalid_data_width ();
        end
        if (SEL_WIDTH != ExpectedSelWidth) begin : g_invalid_sel_width
            mux_sel_width_must_match_num_inputs invalid_sel_width ();
        end
        if (^DEFAULT_VALUE === 1'bx) begin : g_invalid_default_value
            mux_default_value_must_be_known invalid_default_value ();
        end
    endgenerate

    always_comb begin
        o_data = DEFAULT_VALUE;
        o_select_valid = 1'b0;

        // A four-state condition executes only for a known, legal selection.
        // Unknown and out-of-range encodings therefore fail closed.
        if ({1'b0, i_select} < (SEL_WIDTH + 1)'(NUM_INPUTS)) begin
            o_data = i_data[i_select];
            o_select_valid = 1'b1;
        end
    end

endmodule
