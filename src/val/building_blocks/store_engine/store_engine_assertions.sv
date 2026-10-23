`timescale 1ns / 1ps

// Native four-state safety assertions run inside the Python-driven simulation.
// Counter copies exercise enabled, disabled and saturating weighted collection.
module store_engine_assertions #(
    parameter int D = 128,
    parameter int N = 8,
    parameter int TAG_WIDTH = 3,
    parameter int ASYNC_RESET = 0,
    localparam int O = $clog2(N + 1)
) (
    input wire i_clk,
    input wire i_rstb,
    input wire run,
    input wire active,
    input wire start,
    input wire finish,
    input wire fail,
    input wire fatal_now,
    input wire o_error,
    input wire agu_valid,
    input wire agu_ready,
    input wire request_accept,
    input wire stream_accept,
    input wire bad_stream,
    input wire response_store,
    input wire retire,
    input wire [TAG_WIDTH-1:0] issue_pointer,
    input wire [TAG_WIDTH-1:0] retire_pointer,
    input wire [N-1:0] allocated,
    input wire [N-1:0] present,
    input wire [N-1:0] issue_select,
    input wire [N-1:0] response_write,
    input wire [O-1:0] o_outstanding,
    input wire [D-1:0] o_mem_req_data,
    input wire [D/8-1:0] o_mem_req_strobe,
    input wire [D/8-1:0] i_stream_keep,
    input wire [19:0] counter_events
);
    wire [159:0] counts;
    wire [159:0] disabled_counts;
    wire [7:0] peak;
    wire [7:0] disabled_peak;
    integer owned;
    bit initialized = 0;
    store_engine_counters #(.WIDTH(8), .ASYNC_RESET(ASYNC_RESET != 0)) u_enabled (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_clear(1'b0),
        .i_events(counter_events),
        .i_stream_bytes(8'($countones(i_stream_keep))),
        .i_occupancy(8'(o_outstanding)),
        .o_counts(counts),
        .o_maximum_occupancy(peak)
    );
    store_engine_counters #(.WIDTH(8), .ASYNC_RESET(ASYNC_RESET != 0)) u_disabled (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b0),
        .i_clear(1'b1),
        .i_events(counter_events),
        .i_stream_bytes(8'($countones(i_stream_keep))),
        .i_occupancy(8'(o_outstanding)),
        .o_counts(disabled_counts),
        .o_maximum_occupancy(disabled_peak)
    );
    if (ASYNC_RESET == 1) begin : g_async
        always @(negedge i_rstb) begin
            if (i_rstb === 1'b0) begin
                owned = 0;
                initialized = 1;
            end
        end
    end
    always @(posedge i_clk) begin
        if (i_rstb === 1'b0) begin
            owned = 0;
            initialized = 1;
        end else if (run && initialized) begin
            assert (request_accept == (agu_valid && agu_ready))
            else $fatal(1, "STORE_ENGINE_HDL: unpaired AGU advance");
            assert (!request_accept || (stream_accept && !bad_stream))
            else $fatal(1, "STORE_ENGINE_HDL: unpaired write");
            assert (!bad_stream || (stream_accept && !request_accept))
            else $fatal(1, "STORE_ENGINE_HDL: malformed write");
            if (request_accept) begin
                assert (issue_pointer < N && !allocated[issue_pointer] && $onehot(issue_select))
                else $fatal(1, "STORE_ENGINE_HDL: tag reuse");
                for (int b = 0; b < D / 8; b++) begin
                    if (o_mem_req_strobe[b]) begin
                        assert (^o_mem_req_data[b*8+:8] !== 1'bx)
                        else $fatal(1, "STORE_ENGINE_PROTOCOL: data byte %0d", b);
                    end else begin
                        assert (o_mem_req_data[b*8+:8] == 0)
                        else $fatal(1, "STORE_ENGINE_HDL: disabled byte");
                    end
                end
            end
            if (response_store) begin
                assert ($onehot(response_write) && |(response_write & allocated) &&
                    !(|(response_write & present)))
                else $fatal(1, "STORE_ENGINE_HDL: illegal response write");
            end
            if (retire) begin
                assert (allocated[retire_pointer] && present[retire_pointer])
                else $fatal(1, "STORE_ENGINE_HDL: retirement without response");
            end
            owned = owned + int'(request_accept) - int'(retire);
            assert (!o_error || !request_accept)
            else $fatal(1, "STORE_ENGINE_HDL: request during drain");
            assert (!finish || (retire && owned == 0 && !fatal_now))
            else $fatal(1, "STORE_ENGINE_HDL: early completion");
            assert (!fail || !active || owned == 0)
            else $fatal(1, "STORE_ENGINE_HDL: early failure");
        end
        #1ps;
        if (initialized && (i_rstb === 1'b0 || run)) begin
            assert (owned >= 0 && owned <= N && int'(o_outstanding) == owned &&
                $countones(allocated) == owned && (present & ~allocated) == 0)
            else $fatal(1, "STORE_ENGINE_HDL: ownership conservation");
            assert (issue_pointer < N && retire_pointer < N)
            else $fatal(1, "STORE_ENGINE_HDL: pointer range");
        end
    end
endmodule
