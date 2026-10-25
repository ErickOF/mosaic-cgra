`timescale 1ns / 1ps
`default_nettype none

// Independently invalidatable lanes compose the released accumulator. Protected
// witnesses cover data, validity and type, without resetting datapath storage.
module vct_accumulator #(
    parameter int LANES = 4,
    parameter int WIDTH = 32,
    parameter int PROTECTION = 0,
    parameter int ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic [LANES-1:0] i_invalidate,
    input logic [LANES-1:0] i_clear,
    input logic [LANES-1:0] i_write,
    input logic [LANES*WIDTH-1:0] i_data,
    input logic i_signed,
    input logic i_saturate,
    output wire [LANES*WIDTH-1:0] o_data,
    output wire [LANES-1:0] o_valid,
    output wire [LANES-1:0] o_signed,
    output wire [LANES-1:0] o_saturate,
    output wire [LANES-1:0] o_bad,
    output wire [LANES-1:0] o_corrected
);
    for (genvar l = 0; l < LANES; l++) begin : g_lane
        wire reset_b = i_rstb &&!i_invalidate[l];
        wire write_lane = i_clear[l] || i_write[l];
        wire [WIDTH-1:0] raw_data;
        wire raw_valid;
        wire raw_signed;
        wire [WIDTH+2:0] witness;
        wire bad;

        accumulator #(.ACC_WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_value (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_clock_enable(write_lane),
            .i_valid(write_lane),
            .i_command(i_clear[l] ? accumulator_pkg::ACC_CLEAR : accumulator_pkg::ACC_LOAD),
            .i_lane_mask(1'b1),
            .i_data(i_data[l*WIDTH+:WIDTH]),
            .i_signed(i_signed),
            .i_saturate(1'b0),
            .o_data(raw_data),
            .o_state_valid(raw_valid),
            .o_state_signed(raw_signed),
            .o_valid(),
            .o_illegal_operation(),
            .o_updated_mask(),
            .o_carry(),
            .o_borrow(),
            .o_overflow(),
            .o_saturated(),
            .o_zero(),
            .o_negative()
        );

        tile_shell_state #(.WIDTH(WIDTH + 3), .PROTECTION(PROTECTION)) u_witness (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(write_lane),
            .i_data({i_saturate, i_signed, 1'b1,
                i_clear[l] ? {WIDTH{1'b0}} : i_data[l*WIDTH+:WIDTH]}),
            .o_data(witness),
            .o_bad(bad),
            .o_corrected(o_corrected[l])
        );

        assign o_data[l*WIDTH+:WIDTH] = witness[WIDTH-1:0];
        assign o_valid[l] = witness[WIDTH];
        assign o_signed[l] = witness[WIDTH+1];
        assign o_saturate[l] = witness[WIDTH+2];
        assign o_bad[l] = bad || raw_valid !== witness[WIDTH] ||
            (witness[WIDTH] && (raw_data !== witness[WIDTH-1:0] ||
            raw_signed !== witness[WIDTH+1]));
    end
endmodule
`default_nettype wire
