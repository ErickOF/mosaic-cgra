`timescale 1ns / 1ps
`default_nettype none
// Priority among classes, with round-robin service after a bounded high burst.
// The final FIFO owns visible payload stability independently of arbitration.
module cpt_egress #(
    parameter DEPTH = 8,
    parameter MAX_BURST = 8,
    parameter PROTECTION = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_enable,
    input logic [4:0] i_valid,
    output wire [4:0] o_ready,
    input logic [1279:0] i_records,
    output wire o_valid,
    input logic i_ready,
    output wire [255:0] o_record,
    output wire o_busy,
    output wire o_fatal
);
    wire [4:0] valid;
    wire [4:0] ready;
    wire [255:0] record[5];
    wire [31:0] count[5];
    wire [4:0] bad;
    wire [4:0] occupied;
    logic [4:0] eligible;
    logic [2:0] highest;
    logic found;
    wire selected_valid;
    wire [2:0] selected;
    wire final_ready;
    logic [15:0] sequence_number;
    logic sequence_exhausted;
    logic sequence_fault;
    wire forwarded = selected == 3 && record[selected][35:32] == 4'd1;
    logic [255:0] sequenced_record;

    always @* begin
        sequenced_record = record[selected];
        if (!forwarded) sequenced_record[112+:16] = sequence_number;
    end

    wire [31:0] final_count;
    wire final_bad;
    logic [4:0] burst;
    wire fire = selected_valid && final_ready && (!sequence_exhausted || forwarded);

    for (genvar s = 0; s < 5; s++) begin : g_source
        tile_shell_queue #(.WIDTH(256), .DEPTH(1), .PROTECTION(PROTECTION)) u_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(i_flush),
            .i_admit(i_enable),
            .i_deliver(i_enable),
            .i_valid(i_valid[s]),
            .o_ready(o_ready[s]),
            .i_data(i_records[s*256+:256]),
            .o_valid(valid[s]),
            .i_ready(ready[s]),
            .o_data(record[s]),
            .o_count(count[s]),
            .o_bad(bad[s])
        );

        assign occupied[s] = count[s] != 0;
        assign ready[s] = fire && selected == 3'(s);
    end

    always @* begin
        highest = '0;
        found = 1'b0;

        for (int s = 0; s < 5; s++) begin
            if (valid[s] &&!found) begin
                highest = 3'(s);
                found = 1'b1;
            end
        end

        eligible = '0;

        if (found) begin
            if (burst < MAX_BURST || (valid & ~(5'b1 << highest)) == 0)
                eligible[highest] = 1'b1;
            else eligible = valid & ~(5'b1 << highest);
        end
    end

    round_robin_arbiter #(.NUM_REQUESTERS(5), .HAS_LOCK(0), .HOLD_PENDING(0)) u_service (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(i_flush),
        .i_request(valid),
        .i_eligible(eligible & {5{i_enable}}),
        .i_lock(5'd0),
        .i_accept(fire),
        .o_grant_valid(selected_valid),
        .o_grant_index(selected)
    );

    always_ff @(posedge i_clk) begin
        if (i_rstb === 1'b0 || i_flush === 1'b1) begin
            burst <= '0;
            sequence_number <= '0;
            sequence_exhausted <= 1'b0;
        end
        else if (fire) begin
            if (!forwarded) begin
                if (sequence_number == 16'hffff) sequence_exhausted <= 1'b1;
                else sequence_number <= sequence_number + 1'b1;
            end

            if (selected != highest) burst <= '0;
            else if (burst < MAX_BURST) burst <= burst + 1'b1;
        end
    end

    tile_shell_queue #(.WIDTH(256), .DEPTH(DEPTH), .PROTECTION(PROTECTION)) u_output (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(i_flush),
        .i_admit(i_enable),
        .i_deliver(i_enable),
        .i_valid(selected_valid && (!sequence_exhausted || forwarded)),
        .o_ready(final_ready),
        .i_data(sequenced_record),
        .o_valid(o_valid),
        .i_ready(i_ready),
        .o_data(o_record),
        .o_count(final_count),
        .o_bad(final_bad)
    );

    always_ff @(posedge i_clk) begin
        if (i_rstb === 1'b0 || i_flush === 1'b1) sequence_fault <= 1'b0;
        else if (sequence_exhausted && selected_valid &&!forwarded) sequence_fault <= 1'b1;
    end

    assign o_busy = |occupied || final_count != 0;
    assign o_fatal = |bad || final_bad || sequence_fault;
endmodule
`default_nettype wire
