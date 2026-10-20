`timescale 1ns / 1ps

// Protocol shell for a replaceable fixed-latency synchronous 1RW backend.
// Read credits reserve capacity before issue; writes never consume credits.
module sram_wrapper #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH = 1024,
    parameter MASK_GRANULARITY = 8,
    parameter TAG_WIDTH = 4,
    parameter READ_LATENCY = 1,
    parameter MAX_OUTSTANDING_READS = 4,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1 && DEPTH >= 1 && MASK_GRANULARITY >= 1 && TAG_WIDTH >= 1 &&
          READ_LATENCY >= 1 && MAX_OUTSTANDING_READS >= READ_LATENCY) === 1'b1) &&
        (^DATA_WIDTH !== 1'bx) && (^DEPTH !== 1'bx) && (^MASK_GRANULARITY !== 1'bx) &&
        (^TAG_WIDTH !== 1'bx) && (^READ_LATENCY !== 1'bx) && (^MAX_OUTSTANDING_READS !== 1'bx) &&
        ((MASK_GRANULARITY > 0 && DATA_WIDTH % MASK_GRANULARITY == 0) === 1'b1) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned WORDS = PARAMETERS_VALID ? DEPTH : 1,
    localparam int unsigned GRANULE_BITS = PARAMETERS_VALID ? MASK_GRANULARITY : 1,
    localparam int unsigned TAG_BITS = PARAMETERS_VALID ? TAG_WIDTH : 1,
    localparam int unsigned LATENCY = PARAMETERS_VALID ? READ_LATENCY : 1,
    localparam int unsigned CREDITS = PARAMETERS_VALID ? MAX_OUTSTANDING_READS : 1,
    localparam int unsigned ADDR_WIDTH = WORDS > 1 ? $clog2(WORDS) : 1,
    localparam int unsigned MASK_WIDTH = DATA_BITS / GRANULE_BITS,
    localparam int unsigned OUTSTANDING_WIDTH = $clog2(64'(CREDITS) + 1)
) (
    input logic i_clk, i_rstb, i_flush,
    input logic i_req_valid,
    output logic o_req_ready,
    input logic i_req_write,
    input logic [ADDR_WIDTH-1:0] i_req_addr,
    input logic [DATA_BITS-1:0] i_req_wdata,
    input logic [MASK_WIDTH-1:0] i_req_wmask,
    input logic [TAG_BITS-1:0] i_req_tag,
    output logic o_req_error,
    output logic o_rsp_valid,
    input logic i_rsp_ready,
    output wire [DATA_BITS-1:0] o_rsp_rdata,
    output wire [TAG_BITS-1:0] o_rsp_tag,
    output wire o_busy,
    output wire [OUTSTANDING_WIDTH-1:0] o_outstanding_reads
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        sram_wrapper_parameters_must_be_valid invalid_parameters ();
    end else begin : g_shell
        localparam int unsigned PTR_WIDTH = CREDITS > 1 ? $clog2(CREDITS) : 1;
        wire active = i_rstb && !i_flush;
        wire address_valid;
        wire [WORDS-1:0] unused_decoded;
        wire [OUTSTANDING_WIDTH-1:0] outstanding, queued;
        wire [2:0] unused_outstanding_events, unused_queue_events;
        wire accepted = active && i_req_valid && o_req_ready;
        wire accepted_read = accepted && !i_req_write;
        wire consumed = o_rsp_valid && i_rsp_ready;
        wire [LATENCY:0] read_valid;
        wire [TAG_BITS-1:0] read_tag [LATENCY+1];
        wire [DATA_BITS-1:0] backend_rdata;
        wire backend_enable = accepted && (!i_req_write ||
            ((^i_req_wmask !== 1'bx) && ((|i_req_wmask) === 1'b1)));
        wire backend_write = backend_enable && i_req_write;
        wire [ADDR_WIDTH-1:0] backend_addr;
        wire [DATA_BITS-1:0] backend_wdata;
        wire [MASK_WIDTH-1:0] backend_wmask;
        wire [DATA_BITS+TAG_BITS-1:0] mature_data = {read_tag[LATENCY], backend_rdata};
        logic [DATA_BITS+TAG_BITS-1:0] responses [CREDITS];
        wire [PTR_WIDTH-1:0] read_pointer, write_pointer;
        wire have_queued = queued != '0;
        wire enqueue = active && read_valid[LATENCY] && (have_queued || !i_rsp_ready);
        wire dequeue = active && have_queued && i_rsp_ready;
        wire [PTR_WIDTH-1:0] read_next = read_pointer == PTR_WIDTH'(CREDITS-1) ? '0 : read_pointer + 1'b1;
        wire [PTR_WIDTH-1:0] write_next = write_pointer == PTR_WIDTH'(CREDITS-1) ? '0 : write_pointer + 1'b1;

        decoder #(.NUM_OUTPUTS(WORDS)) u_address (
            .i_enable(1'b1),
            .i_select(i_req_addr),
            .o_decoded(unused_decoded),
            .o_select_valid(address_valid)
        );
        always_comb begin
            o_req_error = active && i_req_valid && !address_valid;
            o_rsp_valid = active && (have_queued || read_valid[LATENCY]);
            o_req_ready = 1'b0;
            if (active && !o_req_error) begin
                case (i_req_valid && i_req_write)
                    1'b0: o_req_ready = outstanding < OUTSTANDING_WIDTH'(CREDITS) || consumed;
                    1'b1: o_req_ready = 1'b1;
                    default: begin end
                endcase
            end
        end
        assign o_outstanding_reads = active ? outstanding : '0;
        assign o_busy = active && outstanding != '0;

        // The final pipeline stage is a fall-through return slot. If the
        // consumer stalls it is captured on the next edge; earlier responses
        // take priority. A queued pop and a new backend return can coincide.
        operand_isolation #(.WIDTH(DATA_BITS+TAG_BITS)) u_response_output (
            .i_data(have_queued ? responses[read_pointer] : mature_data),
            .i_isolate(!o_rsp_valid),
            .o_data({o_rsp_tag, o_rsp_rdata})
        );

        counter #(.WIDTH(OUTSTANDING_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_outstanding (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(accepted_read ^ consumed),
            .i_clear(i_flush),
            .i_load(1'b0),
            .i_direction(consumed),
            .i_load_value('0),
            .o_count(outstanding),
            .o_overflow(unused_outstanding_events[0]),
            .o_underflow(unused_outstanding_events[1]),
            .o_terminal(unused_outstanding_events[2])
        );

        counter #(.WIDTH(OUTSTANDING_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_queued (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(enqueue ^ dequeue),
            .i_clear(i_flush),
            .i_load(1'b0),
            .i_direction(dequeue),
            .i_load_value('0),
            .o_count(queued),
            .o_overflow(unused_queue_events[0]),
            .o_underflow(unused_queue_events[1]),
            .o_terminal(unused_queue_events[2])
        );

        dff #(.WIDTH(PTR_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_read_pointer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_flush || dequeue),
            .i_d(i_flush ? {PTR_WIDTH{1'b0}} : read_next),
            .o_q(read_pointer)
        );

        dff #(.WIDTH(PTR_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_write_pointer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_flush || enqueue),
            .i_d(i_flush ? {PTR_WIDTH{1'b0}} : write_next),
            .o_q(write_pointer)
        );

        always_ff @(posedge i_clk) begin
            if (enqueue) responses[write_pointer] <= mature_data;
        end

        dff #(.WIDTH(LATENCY+1), .ASYNC_RESET(ASYNC_RESET != 0)) u_read_valid (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_flush || accepted_read || (|read_valid)),
            .i_d(i_flush ? {(LATENCY+1){1'b0}} : {read_valid[LATENCY-1:0], accepted_read}),
            .o_q(read_valid)
        );

        for (genvar stage = 0; stage <= LATENCY; stage++) begin : g_tag
            wire load_tag;
            wire [TAG_BITS-1:0] next_tag;
            if (stage == 0) begin : g_first
                assign load_tag = accepted_read;
                assign next_tag = i_req_tag;
            end else begin : g_later
                assign load_tag = read_valid[stage-1];
                assign next_tag = read_tag[stage-1];
            end

            dff #(.WIDTH(TAG_BITS), .ASYNC_RESET(ASYNC_RESET != 0)) u_tag (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_flush || load_tag),
                .i_d(i_flush ? {TAG_BITS{1'b0}} : next_tag),
                .o_q(read_tag[stage])
            );
        end

        // Clamp idle address and masked write lanes before the replaceable
        // backend. A zero-mask write is accepted but issues no physical access.
        operand_isolation #(.WIDTH(ADDR_WIDTH)) u_backend_address (
            .i_data(i_req_addr),
            .i_isolate(!backend_enable),
            .o_data(backend_addr)
        );

        operand_isolation #(.WIDTH(MASK_WIDTH)) u_backend_mask (
            .i_data(i_req_wmask),
            .i_isolate(!backend_write),
            .o_data(backend_wmask)
        );

        for (genvar granule = 0; granule < MASK_WIDTH; granule++) begin : g_write_data
            operand_isolation #(.WIDTH(GRANULE_BITS)) u_data (
                .i_data(i_req_wdata[granule*GRANULE_BITS+:GRANULE_BITS]),
                .i_isolate(!(backend_write && backend_wmask[granule])),
                .o_data(backend_wdata[granule*GRANULE_BITS+:GRANULE_BITS])
            );
        end

        sram_wrapper_backend #(
            .DATA_WIDTH(DATA_BITS),
            .DEPTH(WORDS),
            .MASK_GRANULARITY(GRANULE_BITS),
            .READ_LATENCY(LATENCY)
        ) u_backend (
            .i_clk(i_clk),
            .i_enable(backend_enable),
            .i_write(backend_write),
            .i_addr(backend_addr),
            .i_wdata(backend_wdata),
            .i_wmask(backend_wmask),
            .o_rdata(backend_rdata)
        );
    end
endmodule
