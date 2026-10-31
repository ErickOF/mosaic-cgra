`timescale 1ns / 1ps
`default_nettype none
// A compact physical output matrix lets an edge node reuse the same registered
// switch as an interior node. The parent maps compact rows to cardinal ports.
module static_mesh_node #(
    parameter int I = 6,
    parameter int O = 6,
    parameter int D = 32,
    parameter int M = 64,
    parameter int CI = 8,
    parameter int PROTECTION = 0,
    parameter int MULTICAST = 1,
    parameter int ASYNC_RESET = 0,
    parameter logic [I*O-1:0] MATRIX = '1,
    localparam int S = $clog2(I)
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_flush,
    input wire i_error_clear,
    input wire i_install,
    input wire i_route_check,
    input wire [O-1:0] i_enable,
    input wire [O*S-1:0] i_select,
    input wire [CI-1:0] i_context,
    output wire o_install_ready,
    output wire o_match,
    input wire [I-1:0] i_valid,
    output wire [I-1:0] o_ready,
    input wire [I*D-1:0] i_data,
    input wire [I*M-1:0] i_metadata,
    output wire [O-1:0] o_valid,
    input wire [O-1:0] i_ready,
    output wire [O*D-1:0] o_data,
    output wire [O*M-1:0] o_metadata,
    output wire [I-1:0] o_buffered,
    output wire o_idle,
    output wire o_bad,
    output wire o_error,
    output wire o_multicast
);
    wire [O-1:0] active_enable;
    wire [O*S-1:0] active_select;
    wire [CI-1:0] active_context;
    wire [I*O-1:0] pending;
    wire [I-1:0] multicast;
    wire [I*O+I-1:0] witness;
    logic [I*O+I-1:0] next_witness;
    wire witness_bad;
    assign o_match = (active_enable === i_enable) && (active_select === i_select) &&
        (active_context === i_context);
    assign o_bad = witness_bad || (witness !== {o_buffered, pending}) ||
        (i_route_check &&!o_match);
    assign o_multicast = |multicast;

    // This independent delivery witness protects pending branches as well as
    // FIFO-valid state; payload itself travels with the link parity field.
    always @* begin
        next_witness = witness;

        for (int source = 0; source < I; source++) begin
            for (int dest = 0; dest < O; dest++) begin
                if (o_valid[dest] && i_ready[dest] && active_select[dest*S+:S] == S'(source))
                    next_witness[source*O+dest] = 1'b0;

                if (i_valid[source] && o_ready[source])
                    next_witness[source*O+dest] = active_enable[dest] &&
                        active_select[dest*S+:S] == S'(source);
            end

            next_witness[I*O+source] = |next_witness[source*O+:O];
        end

        if (i_flush) next_witness = '0;
    end

    banked_scratchpad_state #(
        .WIDTH(I * O + I),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_witness (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(next_witness),
        .o_data(witness),
        .o_bad(witness_bad)
    );

    local_switch #(
        .NUM_INPUTS(I),
        .NUM_OUTPUTS(O),
        .DATA_WIDTH(D),
        .METADATA_WIDTH(M),
        .CONTEXT_ID_WIDTH(CI),
        .CONNECTIVITY_MASK(MATRIX),
        .SUPPORT_MULTICAST(MULTICAST),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_switch (
        .i_clk(i_clk),
        .i_rstb(i_reset_n),
        .i_flush(i_flush),
        .i_error_clear(i_error_clear),
        .i_config_valid(i_install),
        .o_config_ready(o_install_ready),
        .i_config_output_enable(i_enable),
        .i_config_output_select(i_select),
        .i_config_context_id(i_context),
        .o_config_accepted(),
        .o_config_rejected(),
        .i_input_valid(i_valid),
        .o_input_ready(o_ready),
        .i_input_data(i_data),
        .i_input_metadata(i_metadata),
        .o_output_valid(o_valid),
        .i_output_ready(i_ready),
        .o_output_data(o_data),
        .o_output_metadata(o_metadata),
        .o_active_output_enable(active_enable),
        .o_active_output_select(active_select),
        .o_active_context_id(active_context),
        .o_input_buffered(o_buffered),
        .o_pending_delivery(pending),
        .o_idle(o_idle),
        .o_quiescent(),
        .o_error(o_error),
        .o_error_code(),
        .o_flushed(),
        .o_event_input_accept(),
        .o_event_output_transfer(),
        .o_event_input_stall(),
        .o_event_output_stall(),
        .o_event_multicast_accept(multicast),
        .o_event_item_complete()
    );
endmodule
`default_nettype wire
