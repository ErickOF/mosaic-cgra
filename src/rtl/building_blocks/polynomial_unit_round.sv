`timescale 1ns / 1ps

// Magnitude rounding avoids the negative-floor behavior of arithmetic shifts.
// Parents validate geometry and constrain shift to less than WIDTH.
module polynomial_unit_round #(
    parameter int WIDTH = 32,
    parameter int SHIFT_WIDTH = 6
) (
    input logic signed [WIDTH-1:0] i_value,
    input logic [SHIFT_WIDTH-1:0] i_shift,
    input logic i_nearest,
    output logic signed [WIDTH-1:0] o_value,
    output logic o_inexact
);
    always_comb begin
        logic [WIDTH:0] magnitude;
        logic [WIDTH:0] retained;
        logic [WIDTH:0] remainder_value;
        logic [WIDTH:0] half_value;

        magnitude = i_value[WIDTH-1] ? -$signed({i_value[WIDTH-1], i_value}) :
            {1'b0, i_value};
        retained = magnitude >> i_shift;
        remainder_value = magnitude & (((WIDTH + 1)'(1) << i_shift) - 1'b1);
        half_value = i_shift == 0 ? '0 : (WIDTH + 1)'(1) << (i_shift - 1'b1);
        o_inexact = remainder_value != 0;

        if (i_shift != 0 && i_nearest && ((remainder_value > half_value) ||
            ((remainder_value == half_value) && retained[0])))
            retained = retained + 1'b1;

        o_value = i_value[WIDTH-1] ? -$signed(retained[WIDTH-1:0]) :
            $signed(retained[WIDTH-1:0]);
    end
endmodule
