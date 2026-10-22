`timescale 1ns / 1ps

// Native simulation safety checks, independent of the Python ordered ledger.
// Fairness belongs to the memory peer, not to these design assertions.
module load_engine_assertions #(
    parameter int N = 8,
    parameter int D = 128,
    parameter int M = 33,
    parameter int TAG_WIDTH = 3,
    parameter int ASYNC_RESET = 0,
    localparam int O = $clog2(N + 1)
) (
    input wire i_clk,
    input wire i_rstb,
    input wire run,
    input wire active,
    input wire o_error,
    input wire agu_error,
    input wire agu_valid,
    input wire agu_ready,
    input wire start,
    input wire finish,
    input wire fail,
    input wire fatal_now,
    input wire request_accept,
    input wire response_accept,
    input wire response_store,
    input wire stream_accept,
    input wire [TAG_WIDTH-1:0] issue_pointer,
    input wire [TAG_WIDTH-1:0] retire_pointer,
    input wire [N-1:0] allocated,
    input wire [N-1:0] present,
    input wire [N-1:0] issue_select,
    input wire [N-1:0] response_select,
    input wire [O-1:0] o_outstanding,
    input wire o_mem_req_valid,
    input wire i_mem_req_ready,
    input wire o_stream_valid,
    input wire i_stream_ready,
    input wire [D-1:0] o_stream_data,
    input wire [D/8-1:0] o_stream_keep,
    input wire o_stream_error,
    input wire o_memory_error_seen,
    input wire i_mem_rsp_error,
    input wire [3:0] response_error,
    input wire [6:0] events
);
    integer owned;
    bit initialized = 0;
    logic [6:0] expected_events;
    logic [12:0] counter_events;
    wire [415:0] counts;
    wire [415:0] disabled_counts;
    wire [31:0] peak;
    wire [31:0] disabled_peak;
    logic [31:0] expected_counts [13];
    logic [31:0] expected_peak;
    integer bytes;

    always @(negedge i_rstb) begin
        if (ASYNC_RESET && (i_rstb === 1'b0)) begin
            owned = 0;
            initialized = 1;
            expected_events = '0;
            expected_peak = '0;
            for (int n = 0; n < 13; n++) expected_counts[n] = '0;
        end
    end

    always_comb begin
        counter_events = '0;
        counter_events[0] = run && start;
        counter_events[1] = run && finish;
        counter_events[2] = run && fail;
        counter_events[3] = request_accept;
        counter_events[4] = response_accept;
        counter_events[5] = stream_accept;
        counter_events[6] = run && o_mem_req_valid && (i_mem_req_ready === 1'b0);
        counter_events[7] = run && (o_outstanding != 0)&&!present[retire_pointer];
        counter_events[8] = run && o_stream_valid && (i_stream_ready === 1'b0);
        counter_events[9] = run && (o_outstanding == O'(N));
        counter_events[10] = response_store && (i_mem_rsp_error === 1'b1);
        counter_events[11] = response_error != 0;
        counter_events[12] = stream_accept;
    end
    load_engine_counters #(.ASYNC_RESET(ASYNC_RESET != 0)) u_enabled_counters (
        .i_clk(i_clk), .i_rstb(i_rstb), .i_enable(1'b1), .i_clear(1'b0),
        .i_events(counter_events), .i_stream_bytes(32'($countones(o_stream_keep))),
        .i_occupancy(32'(o_outstanding)), .o_counts(counts), .o_maximum_occupancy(peak)
    );
    load_engine_counters #(.ASYNC_RESET(ASYNC_RESET != 0)) u_disabled_counters (
        .i_clk(i_clk), .i_rstb(i_rstb), .i_enable(1'b0), .i_clear(1'b1),
        .i_events(counter_events), .i_stream_bytes(32'($countones(o_stream_keep))),
        .i_occupancy(32'(o_outstanding)), .o_counts(disabled_counts),
        .o_maximum_occupancy(disabled_peak)
    );

    always @(posedge i_clk) begin
        if (i_rstb === 1'b0) begin
            owned = 0;
            initialized = 1;
            expected_events = '0;
            expected_peak = '0;
            for (int n = 0; n < 13; n++) expected_counts[n] = '0;
        end else if (run && initialized) begin
            assert (request_accept == (agu_ready && agu_valid))
                else $fatal(1, "AGU advanced without matching request");
            if (request_accept) begin
                assert (issue_pointer < N && allocated[issue_pointer] == 0)
                    else $fatal(1, "Allocated tag reused before retirement");
                assert ($onehot(issue_select)) else $fatal(1, "Issue decode not one-hot");
            end
            if (response_store)
                assert ($onehot(response_select) && ( | (response_select & allocated)) &&
                    !( | (response_select & present))) else $fatal(1, "Invalid response write");
            if (stream_accept)
                assert (allocated[retire_pointer] && present[retire_pointer])
                    else $fatal(1, "Retired entry without response");
            if (o_stream_valid && o_stream_error)
                assert (o_stream_data == '0) else $fatal(1, "Memory error leaked data");
            if (o_error)
                assert (!request_accept) else $fatal(1, "Issued during fatal drain");
            owned = owned + int'(request_accept) - int'(stream_accept);
            if (finish)
                assert (stream_accept && owned == 0&&!fatal_now)
                    else $fatal(1, "Completion before final retirement");
            if (fail && active)
                assert (owned == 0 && (o_error || fatal_now))
                    else $fatal(1, "Failure before drain");
            expected_events = {start, request_accept, response_accept, stream_accept, finish,
                finish && o_memory_error_seen, fail};
            bytes = $countones(o_stream_keep);
            for (int n = 0; n < 13; n++)
                if (counter_events[n]) expected_counts[n] = expected_counts[n] +
                    (n == 12 ? 32'(bytes) : 32'd1);
            if (32'(o_outstanding) > expected_peak) expected_peak = 32'(o_outstanding);
        end
        #1ps;
        if (initialized && (i_rstb === 1'b0 || run)) begin
            assert (owned >= 0 && owned <= N && int'(o_outstanding) == owned &&
                $countones(allocated) == owned && (present & ~allocated) == '0)
                else $fatal(1, "Reorder ownership conservation failure");
            assert (events == expected_events) else $fatal(1, "Incorrect event pulse");
            assert (issue_pointer < N && retire_pointer < N)
                else $fatal(1, "Pointer outside implemented tag table");
            for (int n = 0; n < 13; n++)
                assert (counts[n*32+:32] == expected_counts[n])
                    else $fatal(1, "Incorrect event-gated performance counter");
            assert (peak == expected_peak && disabled_counts == '0 && disabled_peak == '0)
                else $fatal(1, "Disabled counters toggled or peak was lost");
        end
    end
endmodule
