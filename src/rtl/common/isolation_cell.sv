`timescale 1ns / 1ps

// Model a technology-independent isolation boundary for power-aware integration.
module isolation_cell #(
    parameter int unsigned WIDTH = 1,
    parameter logic [WIDTH-1:0] CLAMP_VALUE = '0,
    parameter bit ISOLATE_ACTIVE_HIGH = 1'b1
) (
    input  wire [WIDTH-1:0] i_data,
    input  wire             i_isolate,
    output wire [WIDTH-1:0] o_data
);
    if (WIDTH < 1) begin : gen_invalid_width
        initial $fatal(1, "WIDTH must be greater than or equal to one");
    end
    if (^CLAMP_VALUE === 1'bx) begin : gen_invalid_clamp
        initial $fatal(1, "CLAMP_VALUE must contain only zero and one bits");
    end

    wire isolation_active = ISOLATE_ACTIVE_HIGH ? i_isolate : ~i_isolate;

    // The conditional operator conservatively merges data and clamp bits for X/Z control.
    assign o_data = isolation_active ? CLAMP_VALUE : i_data;
endmodule
