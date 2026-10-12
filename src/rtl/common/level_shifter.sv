`timescale 1ns / 1ps

// Model a unidirectional voltage crossing without embedding technology cells.
module level_shifter #(
    parameter int unsigned WIDTH = 1,
    parameter int unsigned DIRECTION = 0
) (
    input  wire [WIDTH-1:0] i_data,
    output wire [WIDTH-1:0] o_data
);
    if (WIDTH < 1) begin : gen_invalid_width
        initial $fatal(1, "WIDTH must be greater than or equal to one");
    end
    if (DIRECTION > 1) begin : gen_invalid_direction
        initial $fatal(1, "DIRECTION must be zero or one");
    end

    assign o_data = i_data;
endmodule
