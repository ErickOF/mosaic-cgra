`timescale 1ns / 1ps

// Internal helper: the parent validates all widths. Parity and data share the
// exact write enable. The sidecar is physically absent in unprotected profiles.
module event_barrier_state #(
    parameter int WIDTH = 1,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0,
    parameter bit PROTECTED = 0,
    parameter bit ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_enable,
    input logic [WIDTH-1:0] i_data,
    output wire [WIDTH-1:0] o_data,
    output wire o_corrupt
);
    dff #(.WIDTH(WIDTH), .RESET_VALUE(RESET_VALUE), .ASYNC_RESET(ASYNC_RESET)) u_data (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(i_enable),
        .i_d(i_data),
        .o_q(o_data)
    );

    if (PROTECTED) begin : g_protection
        wire generated;
        wire stored;
        wire error_bit;
        wire unused_any_error;
        wire unused_no_error;
        wire unused_valid;
        wire [WIDTH-1:0] unused_checked;

        parity #(.DATA_WIDTH(WIDTH), .PARITY_GRANULE_WIDTH(WIDTH)) u_parity (
            .i_generate_data(i_data),
            .i_check_data(o_data),
            .i_check_parity(stored),
            .o_generated_parity(generated),
            .o_checked_data(unused_checked),
            .o_error_vector(error_bit),
            .o_granule_valid(unused_valid),
            .o_no_error(unused_no_error),
            .o_any_error(unused_any_error)
        );

        dff #(.WIDTH(1), .RESET_VALUE( ^ RESET_VALUE), .ASYNC_RESET(ASYNC_RESET)) u_parity_bit (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_enable),
            .i_d(generated),
            .o_q(stored)
        );

        assign o_corrupt = error_bit !== 1'b0;
    end else begin : g_unprotected
        assign o_corrupt = 1'b0;
    end
endmodule
