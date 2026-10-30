`timescale 1ns / 1ps
// Reuse the shell's striped parity/SECDED codec. Only the protected validity
// witness resets; payload storage initializes on the first released clock edge.
module banked_scratchpad_state #(
    parameter int WIDTH = 32,
    parameter int PROTECTION = 0,
    parameter int ASYNC_RESET = 0,
    localparam int CODE = ecc_pkg::code_width(WIDTH, PROTECTION),
    localparam int VALID_CODE = PROTECTION == 2 ? 4 : PROTECTION == 1 ? 2 : 1
) (
    input logic i_clk,
    input logic i_reset_n,
    input logic [WIDTH-1:0] i_data,
    output wire [WIDTH-1:0] o_data,
    output wire o_bad
);
    wire [VALID_CODE-1:0] encoded_valid;
    wire [VALID_CODE-1:0] stored_valid;
    wire valid;
    wire valid_bad;
    wire valid_corrected;
    wire [CODE-1:0] encoded;
    wire [CODE-1:0] stored;
    wire [WIDTH-1:0] decoded;
    wire bad;
    wire corrected;

    tile_shell_codec #(.WIDTH(1), .PROTECTION(PROTECTION)) u_valid_codec (
        .i_data(1'b1),
        .o_code(encoded_valid),
        .i_code(stored_valid),
        .o_data(valid),
        .o_bad(valid_bad),
        .o_corrected(valid_corrected)
    );

    dff #(.WIDTH(VALID_CODE), .ASYNC_RESET(ASYNC_RESET)) u_valid (
        .i_clk(i_clk),
        .i_rstb(i_reset_n),
        .i_enable(1'b1),
        .i_d(encoded_valid),
        .o_q(stored_valid)
    );

    tile_shell_codec #(.WIDTH(WIDTH), .PROTECTION(PROTECTION)) u_codec (
        .i_data(i_data),
        .o_code(encoded),
        .i_code(stored),
        .o_data(decoded),
        .o_bad(bad),
        .o_corrected(corrected)
    );

    dff #(.WIDTH(CODE)) u_payload (
        .i_clk(i_clk),
        .i_rstb(1'b1),
        .i_enable(i_reset_n === 1'b1 && !valid_bad && (!valid || !bad) &&
            !(valid_corrected && corrected)),
        .i_d(encoded), .o_q(stored)
    );

    assign o_data = valid || valid_bad ? decoded : {WIDTH{1'b0}};
    assign o_bad = valid_bad || (valid && bad) || (valid_corrected && corrected);
endmodule
