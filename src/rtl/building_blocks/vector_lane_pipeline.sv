`timescale 1ns / 1ps
`default_nettype none

// Enabled-edge path alignment. Valid and low control bits reset; numerical data
// is unreset and captured only for a valid incoming stage. DEPTH=0 has no state.
module vector_lane_pipeline #(
    parameter int WIDTH = 32,
    parameter int CONTROL_WIDTH = 1,
    parameter int DEPTH = 1,
    parameter bit ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [WIDTH-1:0] i_data,
    output wire o_valid,
    output wire [WIDTH-1:0] o_data
);
    if (DEPTH == 0) begin : g_bypass
        wire [2:0] unused_clock_controls = {i_clk, i_rstb, i_clock_enable};
        assign o_valid = i_valid;
        assign o_data = i_data;
    end else begin : g_pipeline
        wire valid[DEPTH+1];
        wire [WIDTH-1:0] payload[DEPTH+1];
        assign valid[0] = i_valid;
        assign payload[0] = i_data;

        for (genvar stage = 0; stage < DEPTH; stage++) begin : g_stage
            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET)) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_clock_enable),
                .i_d(valid[stage]),
                .o_q(valid[stage+1])
            );

            dff #(.WIDTH(CONTROL_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_control (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_clock_enable),
                .i_d(valid[stage] ? payload[stage][CONTROL_WIDTH-1:0] : '0),
                .o_q(payload[stage+1][CONTROL_WIDTH-1:0])
            );

            if (WIDTH > CONTROL_WIDTH) begin : g_data
                dff #(.WIDTH(WIDTH - CONTROL_WIDTH)) u_data (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(i_clock_enable && i_rstb && valid[stage]),
                    .i_d(payload[stage][WIDTH-1:CONTROL_WIDTH]),
                    .o_q(payload[stage+1][WIDTH-1:CONTROL_WIDTH])
                );
            end
        end

        assign o_valid = valid[DEPTH];
        assign o_data = payload[DEPTH];
    end
endmodule
`default_nettype wire
