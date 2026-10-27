`timescale 1ns / 1ps
`default_nettype none
// Reassemble before exposure: a bad packet never reaches a native endpoint.
module configuration_network_receiver #(
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
    input wire [LINK-1:0] i_flit,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_packet,
    output wire [ENVELOPE-1:0] o_envelope,
    output wire o_frame_error,
    output wire o_idle,
    output wire o_bad
);
    typedef struct packed {
        logic full;
        logic assembling;
        logic error;
        logic [IX-1:0] next_index;
        logic [ENVELOPE-1:0] envelope;
    } state_t;
    state_t q;
    state_t n;
    logic [WIDTH-1:0] packet;
    wire run = i_reset_n === 1'b1 && i_run &&!i_flush &&!o_bad;
    wire take = i_valid === 1'b1 && o_ready;
    wire [IX-1:0] index = i_flit[FLIT+2+:IX];
    wire start = i_flit[FLIT];
    wire last = i_flit[FLIT+1];
    wire [ENVELOPE-1:0] envelope = i_flit[FLIT+2+IX+:ENVELOPE];
    wire known_header = (^{index, start, last, envelope} !== 1'bx);
    wire correct = known_header && i_flit[LINK-1] === PACKET_TYPE && index == q.next_index &&
        start == !q.assembling && last == (index == IX'(FLITS - 1)) &&
        (!q.assembling || envelope == q.envelope);
    assign o_ready = run &&!q.full;
    assign o_valid = run && q.full;
    assign o_packet = o_valid ? packet : '0;
    assign o_envelope = o_valid ? q.envelope : '0;
    assign o_frame_error = q.error;
    assign o_idle = !q.full &&!q.assembling;
    always @* begin
        n = q;
        if (o_valid && i_ready === 1'b1) begin
            n.full = 1'b0;
            n.error = 1'b0;
        end
        if (take) begin
            if (!q.assembling) n.envelope = envelope;
            n.error = q.error || !correct;
            n.assembling = 1'b1;
            n.next_index = q.next_index + 1'b1;
            // Count accepted flits, never trust a corrupt end marker for length.
            if (q.next_index == IX'(FLITS - 1)) begin
                n.full = 1'b1;
                n.assembling = 1'b0;
                n.next_index = '0;
            end
        end
        if (i_flush) n = '0;
    end
    always_ff @(posedge i_clk)
        if (i_reset_n === 1'b1 && take)
            packet[int'(q.next_index)*FLIT+:FLIT] <= i_flit[0+:FLIT];
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
