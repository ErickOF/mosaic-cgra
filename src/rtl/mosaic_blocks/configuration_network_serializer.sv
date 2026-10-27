`timescale 1ns / 1ps
`default_nettype none
// Exactly one packet owns this link through its final accepted flit.
module configuration_network_serializer #(
    parameter int WIDTH = 320,
    parameter int FLIT = 64,
    parameter int ENVELOPE = 64,
    parameter bit PACKET_TYPE = 0,
    parameter int PROTECTION = 1,
    parameter int ASYNC_RESET = 0,
    localparam int FLITS = (WIDTH + FLIT - 1) / FLIT,
    localparam int IX = FLITS > 1 ? $clog2(FLITS) : 1,
    localparam int LINK = FLIT + ENVELOPE + IX + 3
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_flush,
    input wire i_run,
    input wire i_valid,
    output wire o_ready,
    input wire [WIDTH-1:0] i_packet,
    input wire [ENVELOPE-1:0] i_envelope,
    output wire o_valid,
    input wire i_ready,
    output wire [LINK-1:0] o_flit,
    output wire o_idle,
    output wire o_bad
);
    typedef struct packed {
        logic valid;
        logic [IX-1:0] index;
    } state_t;
    state_t q;
    state_t n;
    logic [WIDTH+ENVELOPE-1:0] stored;
    wire run = i_reset_n === 1'b1 && i_run &&!i_flush &&!o_bad;
    wire fire = o_valid && i_ready === 1'b1;
    wire take = i_valid === 1'b1 && o_ready;
    assign o_ready = run &&!q.valid;
    assign o_valid = run && q.valid;
    assign o_idle = !q.valid;
    assign o_flit = o_valid ? {PACKET_TYPE, stored[WIDTH+:ENVELOPE], q.index,
        q.index == IX'(FLITS - 1), q.index == 0,
        stored[int'(q.index)*FLIT+:FLIT]} : '0;
    always @* begin
        n = q;
        if (i_flush) n = '0;
        else if (fire) begin
            if (q.index == IX'(FLITS - 1)) n = '0;
            else n.index = q.index + 1'b1;
        end
        if (take) begin
            n.valid = 1'b1;
            n.index = '0;
        end
    end
    always_ff @(posedge i_clk)
        if (i_reset_n === 1'b1 && take) stored <= {i_envelope, i_packet};
    banked_scratchpad_state #(
        .WIDTH($bits(state_t)),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_state (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(n),
        .o_data(q),
        .o_bad(o_bad)
    );
endmodule
`default_nettype wire
