`timescale 1ns / 1ps
// Independent admission and delivery enables let drain retire already accepted
// records. Zero-depth channels are explicit combinational paths; buffering and
// loop analysis are part of the integration profile.
module tile_shell_queue #(
    parameter int WIDTH = 32,
    parameter int DEPTH = 1,
    parameter int PROTECTION = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_admit,
    input logic i_deliver,
    input logic i_valid,
    output wire o_ready,
    input logic [WIDTH-1:0] i_data,
    output wire o_valid,
    input logic i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire [31:0] o_count,
    output wire o_bad,
    output wire o_corrected
);
    if (DEPTH == 0) begin : g_wire
        assign o_ready = i_rstb &&!i_flush && i_admit && i_deliver && i_ready;
        assign o_valid = i_rstb &&!i_flush && i_admit && i_deliver && i_valid;
        assign o_data = o_valid ? i_data : '0;
        assign o_count = '0;
        assign o_bad = 1'b0;
        assign o_corrected = 1'b0;
    end else begin : g_buffer
        localparam int CODE = ecc_pkg::code_width(WIDTH, PROTECTION);
        wire [CODE-1:0] encoded;
        wire [CODE-1:0] received;
        wire [WIDTH-1:0] decoded;
        wire raw_ready;
        wire raw_valid;
        wire raw_bad;
        wire bad;
        wire corrected;
        wire [$clog2(DEPTH+1)-1:0] occupancy;

        tile_shell_codec #(.WIDTH(WIDTH), .PROTECTION(PROTECTION)) u_codec (
            .i_data(i_data),
            .o_code(encoded),
            .i_code(received),
            .o_data(decoded),
            .o_bad(bad),
            .o_corrected(corrected)
        );

        event_barrier_queue #(.WIDTH(CODE), .DEPTH(DEPTH), .PROTECTED(PROTECTION != 0)) u_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(i_flush),
            .i_valid(i_valid && i_admit &&!i_flush),
            .o_ready(raw_ready),
            .i_data(encoded),
            .o_valid(raw_valid),
            .i_ready(i_ready && i_deliver &&!o_bad &&!i_flush),
            .o_data(received),
            .o_occupancy(occupancy),
            .o_corrupt(raw_bad),
            .o_occupied(),
            .o_contents()
        );

        assign o_bad = raw_bad || (raw_valid && bad);
        assign o_corrected = raw_valid && corrected;
        assign o_ready = i_rstb &&!i_flush && i_admit && raw_ready &&!o_bad;
        assign o_valid = i_rstb &&!i_flush && i_deliver && raw_valid &&!o_bad;
        assign o_data = o_valid ? decoded : '0;
        assign o_count = 32'(occupancy);
    end
endmodule
