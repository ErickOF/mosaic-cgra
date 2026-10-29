`timescale 1ns / 1ps
// Critical completions have reserved storage, independent of phase telemetry.
// The first fatal event has a separate mailbox. Arbitration cannot preempt a
// stalled event; sequence numbers describe delivery order, including priority.
module cluster_power_manager_events #(
    parameter int DEPTH = 8,
    parameter int PROTECTION = 0,
    localparam int WIDTH = $bits(cluster_power_manager_pkg::event_t)
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_normal_valid,
    output wire o_normal_ready,
    input wire [WIDTH-1:0] i_normal,
    input wire i_terminal_valid,
    output wire o_terminal_ready,
    output wire o_terminal_capacity,
    input wire [WIDTH-1:0] i_terminal,
    input wire i_fatal_valid,
    input wire [WIDTH-1:0] i_fatal,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_event,
    output wire o_empty,
    output wire o_overflow,
    output wire o_bad,
    output wire o_exhausted
);
    import cluster_power_manager_pkg::*;
    wire normal_valid;
    wire terminal_valid;
    wire [WIDTH-1:0] normal;
    wire [WIDTH-1:0] terminal;
    wire [1:0] terminal_count;
    wire normal_bad;
    wire terminal_bad;
    wire fatal_bad;
    wire fatal_corrected;
    wire [WIDTH:0] fatal_q;
    logic [WIDTH:0] fatal_d;
    wire [2:0] selection_q;
    logic [2:0] selection_d;
    logic [1:0] selection;
    logic selected_valid;
    event_t selected;
    wire [15:0] sequence_value;
    wire sequence_max;
    wire sequence_overflow;
    wire exhausted;
    wire overflow;
    wire fire = o_valid && i_ready;
    wire fatal_valid = fatal_q[WIDTH];

    always @* begin
        selection = selection_q[2] ? selection_q[1:0] :
            fatal_valid ? 2'd2 : terminal_valid ? 2'd1 : 2'd0;
        selected_valid = 0;
        selected = '0;

        case (selection)
            0: begin
                selected_valid = normal_valid && !normal_bad;
                selected = normal;
            end
            1: begin
                selected_valid = terminal_valid && !terminal_bad;
                selected = terminal;
            end
            2: begin
                selected_valid = fatal_valid && !fatal_bad;
                selected = fatal_q[WIDTH-1:0];
            end
            default: begin end
        endcase

        selected.sequence_id = sequence_value;
        selection_d = selected_valid && !i_ready ? {1'b1, selection} : 3'b0;
        fatal_d = fatal_q;

        if (fire && selection == 2) fatal_d[WIDTH] = 0;

        if (i_fatal_valid && !fatal_q[WIDTH]) fatal_d = {1'b1, i_fatal};
    end

    assign o_valid = i_rstb && selected_valid && !exhausted;
    assign o_event = selected;
    assign o_empty = !normal_valid && !terminal_valid && !fatal_valid;
    assign o_terminal_capacity = terminal_count == 0;
    assign o_bad = normal_bad || terminal_bad || fatal_bad;
    assign o_exhausted = exhausted;
    assign o_overflow = overflow;

    tile_shell_state #(
        .WIDTH(WIDTH + 1),
        .PROTECTION(PROTECTION)
    ) u_fatal (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(fatal_q != fatal_d || fatal_corrected),
        .i_data(fatal_d),
        .o_data(fatal_q),
        .o_bad(fatal_bad),
        .o_corrected(fatal_corrected)
    );

    dff #(
        .WIDTH(3)
    ) u_selection (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(selection_q != selection_d),
        .i_d(selection_d),
        .o_q(selection_q)
    );

    dff u_overflow (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable((i_normal_valid && !o_normal_ready) ||
            (i_terminal_valid && !o_terminal_ready)),
        .i_d(1'b1),
        .o_q(overflow)
    );

    counter #(
        .WIDTH(16),
        .SATURATE(1)
    ) u_sequence (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(fire),
        .i_clear(1'b0),
        .i_load(1'b0),
        .i_direction(1'b0),
        .i_load_value(16'b0),
        .o_count(sequence_value),
        .o_overflow(sequence_overflow),
        .o_underflow(),
        .o_terminal(sequence_max)
    );

    dff u_exhausted (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(fire && sequence_max),
        .i_d(1'b1),
        .o_q(exhausted)
    );

    event_barrier_queue #(
        .WIDTH(WIDTH),
        .DEPTH(DEPTH),
        .PROTECTED(PROTECTION != 0)
    ) u_normal (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_valid(i_normal_valid),
        .o_ready(o_normal_ready),
        .i_data(i_normal),
        .o_valid(normal_valid),
        .i_ready(fire && selection == 0),
        .o_data(normal),
        .o_occupancy(),
        .o_corrupt(normal_bad),
        .o_occupied(),
        .o_contents()
    );

    event_barrier_queue #(
        .WIDTH(WIDTH),
        .DEPTH(2),
        .PROTECTED(PROTECTION != 0)
    ) u_terminal (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_valid(i_terminal_valid),
        .o_ready(o_terminal_ready),
        .i_data(i_terminal),
        .o_valid(terminal_valid),
        .i_ready(fire && selection == 1),
        .o_data(terminal),
        .o_occupancy(terminal_count),
        .o_corrupt(terminal_bad),
        .o_occupied(),
        .o_contents()
    );
endmodule
