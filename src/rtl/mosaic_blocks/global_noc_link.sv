`timescale 1ns / 1ps
`default_nettype none

// The parent validates geometry. Credit stages never stall and never add credits.
// Ready/valid links break the reverse combinational path with the common skid
// buffer, followed by the requested number of elastic, registered forward stages.
module global_noc_link #(
    parameter int WIDTH = 32,
    parameter int FLOW_CONTROL = 1,
    parameter int STAGES = 0
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_flush,
    input wire i_valid,
    output wire o_ready,
    input wire [WIDTH-1:0] i_data,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire o_busy
);
    wire [STAGES:0] valid;
    wire [WIDTH-1:0] data[STAGES+1];
    wire [STAGES:0] ready;
    wire active = i_rstb &&!i_flush;
    assign o_valid = active && valid[STAGES];
    assign o_data = o_valid ? data[STAGES] : '0;
    assign ready[STAGES] = i_ready;
    assign o_busy = |valid;

    if (FLOW_CONTROL == 0) begin : g_elastic
        wire skid_ready;

        skid_buffer #(.DATA_WIDTH(WIDTH)) u_skid (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_valid(i_valid && active),
            .o_ready(skid_ready),
            .i_data(i_data),
            .o_valid(valid[0]),
            .i_ready(ready[0] || i_flush),
            .o_data(data[0])
        );

        assign o_ready = active && skid_ready;

        for (genvar s = 0; s < STAGES; s++) begin : g_stage
            wire [1:0] occupancy;
            wire accept = occupancy < 2;
            wire unused_ready;
            assign ready[s] = accept && active;

            event_barrier_queue #(.WIDTH(WIDTH), .DEPTH(2)) u_queue (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_flush(i_flush),
                .i_valid(valid[s] && accept && active),
                .o_ready(unused_ready),
                .i_data(data[s]),
                .o_valid(valid[s+1]),
                .i_ready(ready[s+1] && active),
                .o_data(data[s+1]),
                .o_occupancy(occupancy),
                .o_corrupt(),
                .o_occupied(),
                .o_contents()
            );
        end
    end else begin : g_credit
        assign valid[0] = i_valid && active;
        assign data[0] = i_data;
        assign o_ready = 1'b0;

        for (genvar s = 0; s < STAGES; s++) begin : g_stage
            dff #(.WIDTH(1)) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(1'b1),
                .i_d(active && valid[s]),
                .o_q(valid[s+1])
            );

            dff #(.WIDTH(WIDTH)) u_data (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(active && valid[s]),
                .i_d(data[s]),
                .o_q(data[s+1])
            );
        end
    end
endmodule
`default_nettype wire
