`timescale 1ns / 1ps
// Only validity resets; invalid protected storage reads as RESET_VALUE. The
// first released edge initializes a codeword even if functional enable is low.
module tile_shell_state #(
    parameter int WIDTH = 32,
    parameter int PROTECTION = 0,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0,
    localparam int STRIPES = (WIDTH + 255) / 256,
    localparam int LAST = WIDTH - (STRIPES - 1) * 256,
    localparam int CODE = PROTECTION == 2 ?
        (STRIPES - 1) * 266 + LAST + hamming_bits(LAST) + 1 : WIDTH + PROTECTION
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_enable,
    input logic [WIDTH-1:0] i_data,
    output wire [WIDTH-1:0] o_data,
    output wire o_bad,
    output wire o_corrected
);
    function automatic int hamming_bits(input int width);
        int bits;
        bits = 1;
        while ((64'd1 << bits) < 64'(width) + 64'(bits) + 1) bits++;
        return bits;
    endfunction
    localparam int VALID_CODE = PROTECTION == 2 ? 4 : PROTECTION == 1 ? 2 : 1;
    wire valid;
    wire [VALID_CODE-1:0] stored_valid;
    wire [VALID_CODE-1:0] encoded_valid;
    wire valid_bad;
    wire valid_corrected;
    tile_shell_codec #(.WIDTH(1), .PROTECTION(PROTECTION)) u_valid_codec (
        .i_data(1'b1),
        .o_code(encoded_valid),
        .i_code(stored_valid),
        .o_data(valid),
        .o_bad(valid_bad),
        .o_corrected(valid_corrected)
    );
    wire [CODE-1:0] encoded;
    wire [CODE-1:0] stored;
    wire [WIDTH-1:0] decoded;
    wire bad;
    wire corrected;
    tile_shell_codec #(.WIDTH(WIDTH), .PROTECTION(PROTECTION)) u_codec (
        .i_data(i_enable ? i_data : RESET_VALUE),
        .o_code(encoded),
        .i_code(stored),
        .o_data(decoded),
        .o_bad(bad),
        .o_corrected(corrected)
    );
    dff #(.WIDTH(VALID_CODE)) u_valid (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_d(encoded_valid),
        .o_q(stored_valid)
    );
    dff #(.WIDTH(CODE)) u_code (
        .i_clk(i_clk),
        .i_rstb(1'b1),
        .i_enable(i_rstb && (i_enable ||!valid)),
        .i_d(encoded),
        .o_q(stored)
    );
    assign o_data = valid || valid_bad ? decoded : RESET_VALUE;
    assign o_bad = valid_bad || (valid && bad) || (valid_corrected && corrected);
    assign o_corrected = !o_bad && (valid_corrected || (valid && corrected));
endmodule
