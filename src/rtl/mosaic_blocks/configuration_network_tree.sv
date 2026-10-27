`timescale 1ns / 1ps
`default_nettype none
// Generated forward multicast and physically separate packet-locked response tree.
module configuration_network_tree #(
    parameter int ENDPOINTS = 20,
    parameter int BRANCH = 4,
    parameter int PROFILE = 1,
    parameter int FORWARD = 160,
    parameter int REVERSE = 160,
    parameter int DESTINATION_OFFSET = 70,
    parameter int LAST_OFFSET = 65,
    parameter int DEPTH = 2,
    parameter int PROTECTION = 1,
    parameter int ASYNC_RESET = 0,
    parameter PRESENT = {ENDPOINTS{1'b1}},
    localparam int LEAVES = leaf_capacity(),
    localparam int INTERNAL = PROFILE == 0 ? (ENDPOINTS > 1 ? ENDPOINTS - 1 : 1) :
        (LEAVES - 1) / (BRANCH - 1),
    localparam int TOTAL = INTERNAL + LEAVES
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_flush,
    input wire i_run,
    input wire i_valid,
    output wire o_ready,
    input wire [FORWARD-1:0] i_flit,
    output wire [ENDPOINTS-1:0] o_endpoint_valid,
    input wire [ENDPOINTS-1:0] i_endpoint_ready,
    output wire [ENDPOINTS*FORWARD-1:0] o_endpoint_flit,
    input wire [ENDPOINTS-1:0] i_response_valid,
    output wire [ENDPOINTS-1:0] o_response_ready,
    input wire [ENDPOINTS*REVERSE-1:0] i_response_flit,
    output wire o_valid,
    input wire i_ready,
    output wire [REVERSE-1:0] o_flit,
    output wire o_idle,
    output wire o_bad,
    output logic [31:0] o_forward_transfers,
    output logic [31:0] o_reverse_transfers
);
    function automatic int leaf_capacity();
        int capacity;
        capacity = BRANCH;

        if (PROFILE == 0) return ENDPOINTS;

        while (capacity < ENDPOINTS) capacity *= BRANCH;

        return capacity;
    endfunction

    function automatic int child(input int node, input int lane);
        if (PROFILE != 0) return node * BRANCH + lane + 1;

        if (lane == 0) return INTERNAL + node;

        if (ENDPOINTS == 1) return TOTAL;

        if (lane != 1) return TOTAL;

        return node + 1 < INTERNAL ? node + 1 : INTERNAL + ENDPOINTS - 1;
    endfunction

    function automatic int parent(input int node);
        if (PROFILE != 0) return (node - 1) / BRANCH;

        if (node < INTERNAL) return node - 1;

        return node - INTERNAL < INTERNAL ? node - INTERNAL : INTERNAL - 1;
    endfunction

    function automatic logic [ENDPOINTS-1:0] route(input int node);
        int current;
        int step;
        int e;
        logic [ENDPOINTS-1:0] result;
        result = '0;

        for (e = 0; e < ENDPOINTS; e++) begin
            current = INTERNAL + e;

            for (step = 0; step < (PROFILE == 0 ? ENDPOINTS + 1 : $clog2(LEAVES) + 2); step++) begin
                if (current == node && PRESENT[e]) result[e] = 1'b1;

                if (current > 0) current = parent(current);
            end
        end

        return result;
    endfunction

    wire [TOTAL-1:0] fv;
    wire [TOTAL-1:0] fr;
    wire [FORWARD-1:0] fd [TOTAL];
    wire [TOTAL-1:0] rv;
    wire [TOTAL-1:0] rr;
    wire [REVERSE-1:0] rd [TOTAL];
    wire [TOTAL*3-1:0] idle;
    wire [TOTAL*3-1:0] bad;
    wire [INTERNAL-1:0] arb_errors;
    wire [INTERNAL-1:0] arb_idle;
    assign fv[0] = i_valid;
    assign fd[0] = i_flit;
    assign o_ready = fr[0];
    assign o_valid = rv[0];
    assign rr[0] = i_ready;
    assign o_flit = o_valid ? rd[0] : '0;

    for (genvar n = 0; n < INTERNAL; n++) begin : g_node
        if (route(n) != 0) begin : g_present
            wire [BRANCH-1:0] selected;
            wire [BRANCH-1:0] valid;
            wire [BRANCH-1:0] ready;
            wire [BRANCH*FORWARD-1:0] raw_data;
            logic [BRANCH*FORWARD-1:0] data;

            always @* data = raw_data;

            wire [BRANCH-1:0] rvalid;
            wire [BRANCH-1:0] rready;
            wire [REVERSE-1:0] rdata [BRANCH];
            wire [BRANCH-1:0] locks;
            wire grant;
            wire [BRANCH-1:0] onehot;
            wire [(BRANCH>1 ? $clog2(BRANCH) : 1)-1:0] index;
            wire pending;
            wire locked;
            assign arb_idle[n] = !pending &&!locked;
            wire arb_bad;
            assign arb_errors[n] = arb_bad;

            configuration_network_fork #(
                .WIDTH(FORWARD),
                .OUTPUTS(BRANCH),
                .PROTECTION(PROTECTION),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_fork (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_flush(i_flush),
                .i_run(i_run),
                .i_valid(fv[n]),
                .o_ready(fr[n]),
                .i_data(fd[n]),
                .i_destination(selected),
                .o_valid(valid),
                .i_ready(ready),
                .o_data(raw_data),
                .o_idle(idle[n*3]),
                .o_bad(bad[n*3])
            );

            for (genvar k = 0; k < BRANCH; k++) begin : g_child
                localparam int NODE = child(n, k);
                localparam logic [ENDPOINTS-1:0] MASK = NODE < TOTAL ? route(NODE) : '0;
                assign selected[k] = (^fd[n][DESTINATION_OFFSET+:ENDPOINTS] !== 1'bx) &&
                    (|(fd[n][DESTINATION_OFFSET+:ENDPOINTS] & MASK));

                if (NODE < TOTAL && MASK != 0) begin : g_present
                    configuration_network_link #(
                        .WIDTH(FORWARD),
                        .DEPTH(DEPTH),
                        .PROTECTION(PROTECTION),
                        .ASYNC_RESET(ASYNC_RESET)
                    ) u_forward (
                        .i_clk(i_clk),
                        .i_reset_n(i_reset_n),
                        .i_flush(i_flush),
                        .i_run(i_run),
                        .i_valid(valid[k]),
                        .o_ready(ready[k]),
                        .i_data(data[k*FORWARD+:FORWARD]),
                        .o_valid(fv[NODE]),
                        .i_ready(fr[NODE]),
                        .o_data(fd[NODE]),
                        .o_idle(idle[NODE*3+1]),
                        .o_bad(bad[NODE*3+1])
                    );

                    configuration_network_link #(
                        .WIDTH(REVERSE),
                        .DEPTH(DEPTH),
                        .PROTECTION(PROTECTION),
                        .ASYNC_RESET(ASYNC_RESET)
                    ) u_reverse (
                        .i_clk(i_clk),
                        .i_reset_n(i_reset_n),
                        .i_flush(i_flush),
                        .i_run(i_run),
                        .i_valid(rv[NODE]),
                        .o_ready(rr[NODE]),
                        .i_data(rd[NODE]),
                        .o_valid(rvalid[k]),
                        .i_ready(rready[k]),
                        .o_data(rdata[k]),
                        .o_idle(idle[NODE*3+2]),
                        .o_bad(bad[NODE*3+2])
                    );
                end else begin : g_absent
                    assign ready[k] = 1'b0;
                    assign rvalid[k] = 1'b0;
                    assign rdata[k] = '0;
                end

                assign locks[k] = rvalid[k] &&!rdata[k][LAST_OFFSET];
                assign rready[k] = i_run &&!i_flush && onehot[k] && rr[n] === 1'b1;
            end

            round_robin_arbiter #(
                .NUM_REQUESTERS(BRANCH),
                .HAS_LOCK(1),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_arbiter (
                .i_clk(i_clk),
                .i_rstb(i_reset_n),
                .i_request(rvalid),
                .i_eligible('1),
                .i_lock(locks),
                .i_accept(rv[n] && rr[n] === 1'b1),
                .i_flush(i_flush),
                .o_grant_valid(grant),
                .o_grant_onehot(onehot),
                .o_grant_index(index),
                .o_grant_lock(),
                .o_grant_accepted(),
                .o_contended(),
                .o_pending(pending),
                .o_locked(locked),
                .o_lock_owner(),
                .o_protocol_error(arb_bad)
            );

            assign rv[n] = i_reset_n === 1'b1 && i_run &&!i_flush && grant;
            assign rd[n] = rv[n] ? rdata[index] : '0;

            // The two root pseudo-link entries have no physical storage.
            if (n == 0) begin : g_root
                assign idle[1+:2] = '1;
                assign bad[1+:2] = '0;
            end
        end else begin : g_absent
            assign fr[n] = 1'b0;
            assign rv[n] = 1'b0;
            assign rd[n] = '0;
            assign idle[n*3] = 1'b1;
            assign bad[n*3] = 1'b0;
            assign arb_idle[n] = 1'b1;
            assign arb_errors[n] = 1'b0;

            if (n == 0) begin : g_root
                assign idle[1+:2] = '1;
                assign bad[1+:2] = '0;
            end
        end
    end

    for (genvar n = INTERNAL; n < TOTAL; n++) begin : g_leaf
        localparam int E = n - INTERNAL;

        if (E < ENDPOINTS && PRESENT[E]) begin : g_present
            assign o_endpoint_valid[E] = fv[n];
            assign o_endpoint_flit[E*FORWARD+:FORWARD] = fv[n] ? fd[n] : '0;
            assign fr[n] = i_endpoint_ready[E];
            assign rv[n] = i_response_valid[E];
            assign rd[n] = i_response_flit[E*REVERSE+:REVERSE];
            assign o_response_ready[E] = rr[n];
        end

        assign idle[n*3] = 1'b1;
        assign bad[n*3] = 1'b0;
    end

    // Sparse subtrees have no instantiated link drivers.
    for (genvar n = 1; n < TOTAL; n++) begin : g_sparse
        if (route(n) == 0) begin : g_tie
            assign fv[n] = 1'b0;
            assign fd[n] = '0;
            assign rr[n] = 1'b0;
            assign idle[n*3+1+:2] = '1;
            assign bad[n*3+1+:2] = '0;

            if (n < INTERNAL) begin : g_internal_unused
                // Empty fork and arbiter stay reset by their inputs.
            end else begin : g_leaf_unused
                assign fr[n] = 1'b0;
                assign rv[n] = 1'b0;
                assign rd[n] = '0;
            end
        end
    end

    for (genvar e = 0; e < ENDPOINTS; e++) begin : g_absent_endpoint
        if (!PRESENT[e]) begin : g_tie
            assign o_endpoint_valid[e] = 1'b0;
            assign o_endpoint_flit[e*FORWARD+:FORWARD] = '0;
            assign o_response_ready[e] = 1'b0;
        end
    end

    always @* begin
        o_forward_transfers = '0;
        o_reverse_transfers = '0;

        for (int n = 1; n < TOTAL; n++) begin
            o_forward_transfers += 32'(fv[n] && fr[n]);
            o_reverse_transfers += 32'(rv[n] && rr[n]);
        end
    end

    assign o_idle = (&idle) && (&arb_idle);
    assign o_bad = (|bad) || (|arb_errors);
endmodule
`default_nettype wire
