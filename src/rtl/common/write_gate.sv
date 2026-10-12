/// Parameterizable architectural write-enable suppressor.
///
/// The integration must assert i_suppress only when dropping the corresponding
/// state update is architecturally legal. This module does not inspect data or
/// create protocol acknowledgements.
module write_gate #(
    parameter int unsigned WIDTH = 1
) (
    input  logic [WIDTH-1:0] i_write_enable,
    input  logic [WIDTH-1:0] i_suppress,
    output logic [WIDTH-1:0] o_write_enable,
    output logic [WIDTH-1:0] o_write_suppressed
);

    generate
        if (WIDTH < 1) begin : g_invalid_width
            write_gate_width_must_be_greater_than_zero invalid_width ();
        end
    endgenerate

    assign o_write_enable = i_write_enable & ~i_suppress;
    assign o_write_suppressed = i_write_enable & i_suppress;

endmodule
