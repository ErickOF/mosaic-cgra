/// Parameterizable architectural operand-isolation primitive.
///
/// This module clamps an inactive operand before an expensive combinational
/// cone. It is not a replacement for UPF isolation at a power-domain boundary.
module operand_isolation #(
    parameter int unsigned WIDTH = 32,
    parameter logic [WIDTH-1:0] CLAMP_VALUE = '0
) (
    input  logic [WIDTH-1:0] i_data,
    input  logic             i_isolate,
    output logic [WIDTH-1:0] o_data
);

    generate
        if (WIDTH < 1) begin : g_invalid_width
            operand_isolation_width_must_be_greater_than_zero invalid_width ();
        end
        if (^CLAMP_VALUE === 1'bx) begin : g_invalid_clamp_value
            operand_isolation_clamp_value_must_be_known invalid_clamp_value ();
        end
    endgenerate

    always_comb begin
        case (i_isolate)
            1'b0: o_data = i_data;
            1'b1: o_data = CLAMP_VALUE;
            default: o_data = 'x;
        endcase
    end

endmodule
