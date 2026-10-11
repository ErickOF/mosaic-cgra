`timescale 1ns / 1ps

// Portable model of visible state plus an explicitly saved retention image.
module retention_register #(
    parameter int unsigned WIDTH = 1,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0,
    parameter bit ASYNC_RESET = 1'b0,
    parameter bit HAS_ENABLE = 1'b1
) (
    input  logic             i_clk,
    input  logic             i_rstb,
    input  logic             i_enable,
    input  logic             i_save,
    input  logic             i_restore,
    input  logic [WIDTH-1:0] i_d,
    output logic [WIDTH-1:0] o_q
);
    logic [WIDTH-1:0] retained_image;

    if (WIDTH < 1) begin : gen_invalid_width
        initial $fatal(1, "WIDTH must be greater than or equal to one");
    end
    if (^RESET_VALUE === 1'bx) begin : gen_invalid_reset_value
        initial $fatal(1, "RESET_VALUE must contain only zero and one bits");
    end

    if (ASYNC_RESET) begin : gen_async_reset
        always_ff @(posedge i_clk or negedge i_rstb) begin
            if (!i_rstb) begin
                o_q <= RESET_VALUE;
                retained_image <= RESET_VALUE;
            end else if (i_restore) begin
                o_q <= retained_image;
            end else if (i_save) begin
                retained_image <= o_q;
            end else if (!HAS_ENABLE || i_enable) begin
                o_q <= i_d;
            end
        end
    end else begin : gen_sync_reset
        always_ff @(posedge i_clk) begin
            if (!i_rstb) begin
                o_q <= RESET_VALUE;
                retained_image <= RESET_VALUE;
            end else if (i_restore) begin
                o_q <= retained_image;
            end else if (i_save) begin
                retained_image <= o_q;
            end else if (!HAS_ENABLE || i_enable) begin
                o_q <= i_d;
            end
        end
    end
endmodule
