`timescale 1ns / 1ps
`default_nettype none
// Explicit remote transactions. A request never writes a participant directly.
// Each live slot reserves its terminal record until egress accepts that record.
module cpt_actions #(
    parameter SLOTS = 4,
    parameter SUPPORT_TIMEOUT = 1,
    localparam int SI = SLOTS > 1 ? $clog2(SLOTS) : 1
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_enable,
    input logic i_issue,
    input cpt_pkg::cpt_record_t i_request,
    input logic [31:0] i_timeout,
    output logic o_issue_ready,
    output logic o_issue_error,
    input logic i_response_valid,
    input cpt_pkg::cpt_record_t i_response,
    output logic o_response_ready,
    output logic o_response_error,
    output logic o_request_valid,
    output cpt_pkg::cpt_record_t o_request,
    input logic i_request_ready,
    output logic o_terminal_valid,
    output cpt_pkg::cpt_record_t o_terminal,
    input logic i_terminal_ready,
    output logic o_busy,
    output logic o_uncertain,
    output logic o_timeout_event
);
    import cpt_pkg::*;
    // All these records depend on the number of outstanding transactions.
    cpt_action_state_t state[SLOTS];
    logic [255:0] requests[SLOTS];
    logic [15:0] safe_mask[SLOTS];
    logic [31:0] threshold[SLOTS];
    wire [31:0] elapsed[SLOTS];
    logic [SLOTS-1:0] queued;
    logic [SLOTS-1:0] terminal;
    logic [SLOTS-1:0] expiry;
    logic [SI-1:0] free_slot;
    logic found_free;
    logic duplicate;
    logic response_match;
    logic [SI-1:0] response_slot;
    wire [SI-1:0] request_slot;
    wire [SI-1:0] terminal_slot;
    wire request_fire = o_request_valid && i_request_ready === 1'b1;
    wire terminal_fire = o_terminal_valid && i_terminal_ready === 1'b1;
    wire issue_fire = i_issue === 1'b1 && o_issue_ready;
    wire response_fire = i_response_valid === 1'b1 && o_response_ready;
    wire reset_b = i_rstb !== 1'b0 && i_flush !== 1'b1;

    always @* begin
        found_free = 1'b0;
        free_slot = '0;
        duplicate = 1'b0;
        response_match = 1'b0;
        response_slot = '0;
        queued = '0;
        terminal = '0;
        expiry = '0;
        o_busy = 1'b0;
        o_uncertain = 1'b0;

        for (int s = 0; s < SLOTS; s++) begin
            if (state[s] == ACTION_FREE &&!found_free) begin
                found_free = 1'b1;
                free_slot = SI'(s);
            end

            if (state[s] != ACTION_FREE) begin
                o_busy = 1'b1;
                duplicate = duplicate || requests[s][128+:8] == i_request.tag;

                if (requests[s][128+:8] == i_response.tag &&
                    requests[s][96+:16] == i_response.epoch &&
                    requests[s][64+:16] == i_response.owner &&
                    requests[s][80+:16] == i_response.context_version &&
                    requests[s][3+:29] == i_response.envelope[31:3] &&
                    requests[s][36+:4] == i_response.opcode &&
                    requests[s][152+:16] == i_response.package_version &&
                    requests[s][168+:16] == i_response.route_version) begin
                    response_match = 1'b1;
                    response_slot = SI'(s);
                end
            end

            queued[s] = state[s] == ACTION_QUEUED || state[s] == ACTION_QUERY;
            terminal[s] = state[s] == ACTION_COMPLETED || state[s] == ACTION_REJECTED;
            expiry[s] = SUPPORT_TIMEOUT && threshold[s] != 0 &&
                elapsed[s] >= threshold[s] && (state[s] == ACTION_SENT ||
                state[s] == ACTION_WAIT_SAFE);
            o_uncertain = o_uncertain || state[s] == ACTION_QUERY ||
                state[s] == ACTION_WAIT_QUERY;
        end
    end

    assign o_issue_error = duplicate || i_request.epoch == 0 ||
        i_request.participants == 0 || i_request.reserved != 0 ||
        ^i_request === 1'bx;
    assign o_issue_ready = i_enable && reset_b && found_free &&!o_issue_error;
    assign o_response_ready = i_enable && reset_b;
    wire legal_response = response_match && ^i_response !== 1'bx &&
        i_response.reserved == 0 &&
        (i_response.kind == CPT_RECORD_SAFE || i_response.kind == CPT_RECORD_RESPONSE);
    assign o_response_error = !legal_response ||!(state[response_slot] == ACTION_SENT
            || state[response_slot] == ACTION_WAIT_SAFE ||
        state[response_slot] == ACTION_WAIT_QUERY) ||
        (i_response.kind == CPT_RECORD_SAFE && (state[response_slot] == ACTION_WAIT_QUERY ||
        i_response.participants == 0 ||
        (i_response.participants & ~requests[response_slot][136+:16]) != 0 ||
        (i_response.participants & safe_mask[response_slot]) != 0)) ||
        (i_response.kind == CPT_RECORD_RESPONSE &&!i_response.flags[0] &&
        state[response_slot] != ACTION_WAIT_QUERY &&
        (safe_mask[response_slot] & requests[response_slot][136+:16]) !=
            requests[response_slot][136+:16]);
    assign o_timeout_event = |expiry && i_enable;

    round_robin_arbiter #(.NUM_REQUESTERS(SLOTS), .HAS_LOCK(0)) u_request_arbiter (
        .i_clk(i_clk),
        .i_rstb(reset_b),
        .i_flush(i_flush),
        .i_request(queued),
        .i_eligible({SLOTS{i_enable}}),
        .i_lock({SLOTS{1'b0}}),
        .i_accept(request_fire),
        .o_grant_valid(o_request_valid),
        .o_grant_index(request_slot)
    );

    round_robin_arbiter #(.NUM_REQUESTERS(SLOTS), .HAS_LOCK(0)) u_terminal_arbiter (
        .i_clk(i_clk),
        .i_rstb(reset_b),
        .i_flush(i_flush),
        .i_request(terminal),
        .i_eligible({SLOTS{i_enable}}),
        .i_lock({SLOTS{1'b0}}),
        .i_accept(terminal_fire),
        .o_grant_valid(o_terminal_valid),
        .o_grant_index(terminal_slot)
    );

    always @* begin
        o_request = requests[request_slot];
        o_request.kind = state[request_slot] == ACTION_QUERY ?
            CPT_RECORD_QUERY : CPT_RECORD_REQUEST;
        o_terminal = requests[terminal_slot];
        o_terminal.kind = CPT_RECORD_TERMINAL;
        o_terminal.flags = state[terminal_slot] == ACTION_REJECTED ? 4'd1 : 4'd0;
    end

    for (genvar s = 0; s < SLOTS; s++) begin : g_slot
        wire new_request = issue_fire && free_slot == SI'(s);
        wire monitor = i_enable && SUPPORT_TIMEOUT && threshold[s] != 0 &&
            (state[s] == ACTION_SENT || state[s] == ACTION_WAIT_SAFE);

        counter #(.WIDTH(32)) u_timeout (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(monitor),
            .i_clear(new_request),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(32'd0),
            .o_count(elapsed[s])
        );

        always_ff @(posedge i_clk) begin
            if (!reset_b) begin
                state[s] <= ACTION_FREE;
                requests[s] <= '0;
                safe_mask[s] <= '0;
                threshold[s] <= '0;
            end else if (i_enable) begin
                if (new_request) begin
                    requests[s] <= i_request;
                    safe_mask[s] <= '0;
                    threshold[s] <= i_timeout;
                    state[s] <= ACTION_QUEUED;
                end

                if (request_fire && request_slot == SI'(s))
                    state[s] <= state[s] == ACTION_QUERY ? ACTION_WAIT_QUERY : ACTION_SENT;

                if (expiry[s]) state[s] <= ACTION_QUERY;

                if (response_fire && legal_response &&!o_response_error &&
                    response_slot == SI'(s)) begin

                    if (i_response.kind == CPT_RECORD_SAFE) begin
                        if (i_response.participants != 0 &&
                            (i_response.participants & ~requests[s][136+:16]) == 0) begin
                            safe_mask[s] <= safe_mask[s] | i_response.participants;
                            state[s] <= ACTION_WAIT_SAFE;
                        end
                    end else if (i_response.flags[0]) begin
                        state[s] <= ACTION_REJECTED;
                    end else if (state[s] == ACTION_WAIT_QUERY ||
                        (safe_mask[s] & requests[s][136+:16]) == requests[s][136+:16]) begin
                        state[s] <= ACTION_COMPLETED;
                    end
                end

                if (terminal_fire && terminal_slot == SI'(s)) state[s] <= ACTION_FREE;
            end
        end
    end
endmodule
`default_nettype wire
