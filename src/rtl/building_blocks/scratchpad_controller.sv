`timescale 1ns / 1ps
`default_nettype none

// Routing and ordered completion shell. Banks remain external so a subsystem may
// choose protection, capacity and physical backends independently. Every attached
// scratchpad_bank must use TAG_WIDTH = BANK_TAG_WIDTH and coordinated reset/flush.
module scratchpad_controller #(
    parameter DATA_WIDTH = 128,
    parameter NUM_BANKS = 8,
    parameter BANK_DEPTH_WORDS = 1024,
    parameter NUM_CLIENTS = 4,
    parameter CLIENT_TAG_WIDTH = 8,
    parameter MAX_OUTSTANDING_PER_CLIENT = 8,
    parameter INTERLEAVE_BYTES = 16,
    parameter MAP_MODE = 0,
    parameter ENFORCE_PERMISSIONS = 1,
    parameter DEFAULT_ALLOW = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 8) === 1'b1) && (((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((((DATA_WIDTH / 8) & ((DATA_WIDTH / 8) - 1)) == 0) === 1'b1) &&
        ((NUM_BANKS > 0) === 1'b1) && (((^NUM_BANKS == 1'b0) || (^NUM_BANKS == 1'b1)) === 1'b1) &&
        ((BANK_DEPTH_WORDS > 0) === 1'b1) && (((^BANK_DEPTH_WORDS == 1'b0) || (^BANK_DEPTH_WORDS == 1'b1)) === 1'b1) &&
        ((NUM_CLIENTS > 0) === 1'b1) && (((^NUM_CLIENTS == 1'b0) || (^NUM_CLIENTS == 1'b1)) === 1'b1) &&
        ((CLIENT_TAG_WIDTH > 0) === 1'b1) && (((^CLIENT_TAG_WIDTH == 1'b0) || (^CLIENT_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((MAX_OUTSTANDING_PER_CLIENT > 0) === 1'b1) &&
        (((^MAX_OUTSTANDING_PER_CLIENT == 1'b0) || (^MAX_OUTSTANDING_PER_CLIENT == 1'b1)) === 1'b1) &&
        ((INTERLEAVE_BYTES > 0) === 1'b1) && (((^INTERLEAVE_BYTES == 1'b0) || (^INTERLEAVE_BYTES == 1'b1)) === 1'b1) &&
        (((INTERLEAVE_BYTES & (INTERLEAVE_BYTES - 1)) == 0) === 1'b1) &&
        ((INTERLEAVE_BYTES >= DATA_WIDTH / 8) === 1'b1) &&
        ((128'(INTERLEAVE_BYTES) <= 128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH / 8))
            === 1'b1) &&
        ((128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH / 8) %
            128'(INTERLEAVE_BYTES > 0 ? INTERLEAVE_BYTES : 1) == 0) === 1'b1) &&
        ((MAP_MODE === 0) || (MAP_MODE === 1)) &&
        ((MAP_MODE == 0 || (NUM_BANKS & (NUM_BANKS - 1)) == 0) === 1'b1) &&
        ((ENFORCE_PERMISSIONS === 0) || (ENFORCE_PERMISSIONS === 1)) &&
        ((DEFAULT_ALLOW === 0) || (DEFAULT_ALLOW === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((128'(NUM_BANKS) * 128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH) <
            128'd2147483647) === 1'b1) &&
        ((128'(NUM_CLIENTS) * 128'(MAX_OUTSTANDING_PER_CLIENT) *
            (128'(DATA_WIDTH) + 128'(CLIENT_TAG_WIDTH) + 128'(NUM_BANKS) + 128) <
            128'd2147483647) === 1'b1) &&
        ((128'(NUM_CLIENTS) * 128'(NUM_BANKS) * 128'(DATA_WIDTH) <
            128'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 8,
    localparam int B = PARAMETERS_VALID ? NUM_BANKS : 1,
    localparam int C = PARAMETERS_VALID ? NUM_CLIENTS : 1,
    localparam int N = PARAMETERS_VALID ? MAX_OUTSTANDING_PER_CLIENT : 1,
    localparam int T = PARAMETERS_VALID ? CLIENT_TAG_WIDTH : 1,
    localparam int WORDS = PARAMETERS_VALID ? BANK_DEPTH_WORDS : 1,
    localparam int STRIPE = PARAMETERS_VALID ? INTERLEAVE_BYTES : 1,
    localparam int DATA_BYTES = D / 8,
    localparam logic [63:0] BANK_CAPACITY_BYTES = 64'(WORDS) * 64'(DATA_BYTES),
    localparam logic [63:0] TOTAL_CAPACITY_BYTES = 64'(B) * BANK_CAPACITY_BYTES,
    localparam int GLOBAL_ADDR_WIDTH = TOTAL_CAPACITY_BYTES > 1 ?
        $clog2(TOTAL_CAPACITY_BYTES) : 1,
    localparam int BANK_ADDR_WIDTH = BANK_CAPACITY_BYTES > 1 ? $clog2(BANK_CAPACITY_BYTES) : 1,
    localparam int SIZE_WIDTH = DATA_BYTES > 1 ? $clog2($clog2(DATA_BYTES) + 1) : 1,
    localparam int CLIENT_INDEX_WIDTH = C > 1 ? $clog2(C) : 1,
    localparam int BANK_INDEX_WIDTH = B > 1 ? $clog2(B) : 1,
    localparam int CLIENT_SLOT_WIDTH = N > 1 ? $clog2(N) : 1,
    localparam int BANK_TAG_WIDTH = CLIENT_INDEX_WIDTH + CLIENT_SLOT_WIDTH,
    localparam int CLIENT_OCCUPANCY_WIDTH = $clog2(64'(N) + 1),
    localparam int PERMISSION_WIDTH = C * B
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_perm_valid,
    output logic o_perm_ready,
    input logic [PERMISSION_WIDTH-1:0] i_read_permission,
    input logic [PERMISSION_WIDTH-1:0] i_write_permission,
    output logic o_permission_updated,
    input logic [C-1:0] i_client_req_valid,
    input logic [C-1:0] i_client_req_write,
    input logic [C*GLOBAL_ADDR_WIDTH-1:0] i_client_req_address,
    input logic [C*SIZE_WIDTH-1:0] i_client_req_size_log2,
    input logic [C*D-1:0] i_client_req_wdata,
    input logic [C*DATA_BYTES-1:0] i_client_req_wstrobe,
    input logic [C*T-1:0] i_client_req_tag,
    output logic [C-1:0] o_client_req_ready,
    output logic [C-1:0] o_client_rsp_valid,
    output logic [C-1:0] o_client_rsp_write,
    output logic [C*D-1:0] o_client_rsp_rdata,
    output logic [C*T-1:0] o_client_rsp_tag,
    output logic [C-1:0] o_client_rsp_error,
    output logic [C*scratchpad_controller_pkg::MEM_ERROR_WIDTH-1:0] o_client_rsp_error_code,
    output logic [C-1:0] o_client_rsp_corrected,
    output logic [C-1:0] o_client_rsp_uncorrectable,
    input logic [C-1:0] i_client_rsp_ready,
    output logic [B-1:0] o_bank_req_valid,
    output logic [B-1:0] o_bank_req_write,
    output logic [B*BANK_ADDR_WIDTH-1:0] o_bank_req_address,
    output logic [B*SIZE_WIDTH-1:0] o_bank_req_size_log2,
    output logic [B*D-1:0] o_bank_req_wdata,
    output logic [B*DATA_BYTES-1:0] o_bank_req_wstrobe,
    output logic [B*BANK_TAG_WIDTH-1:0] o_bank_req_tag,
    input logic [B-1:0] i_bank_req_ready,
    input logic [B-1:0] i_bank_rsp_valid,
    input logic [B-1:0] i_bank_rsp_write,
    input logic [B*D-1:0] i_bank_rsp_rdata,
    input logic [B*BANK_TAG_WIDTH-1:0] i_bank_rsp_tag,
    input logic [B-1:0] i_bank_rsp_error,
    input logic [B*scratchpad_bank_pkg::BANK_ERROR_WIDTH-1:0] i_bank_rsp_error_code,
    input logic [B-1:0] i_bank_rsp_corrected,
    input logic [B-1:0] i_bank_rsp_uncorrectable,
    output logic [B-1:0] o_bank_rsp_ready,
    output logic [B-1:0] o_bank_flush,
    input logic [B-1:0] i_bank_flush_completed,
    input logic [B-1:0] i_bank_idle,
    output logic o_idle,
    output logic o_busy,
    output logic o_flushing,
    output logic o_flush_completed,
    output logic [C*CLIENT_OCCUPANCY_WIDTH-1:0] o_client_outstanding,
    output logic [B-1:0] o_bank_conflict,
    output logic [C-1:0] o_request_accepted,
    output logic [C-1:0] o_response_accepted,
    output logic [C-1:0] o_permission_denied,
    output logic o_error,
    output logic [scratchpad_controller_pkg::CTRL_ERROR_WIDTH-1:0] o_error_code
 );
    import scratchpad_controller_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        scratchpad_controller_parameters_must_be_valid invalid_parameters ();
    end else begin : g_controller
        // Parameterized payload types stay beside their geometry.
        typedef struct packed {
            logic [T-1:0] tag;
            logic write;
            logic [BANK_INDEX_WIDTH-1:0] bank;
        } metadata_t;

        typedef struct packed {
            logic [D-1:0] data;
            logic error;
            logic [MEM_ERROR_WIDTH-1:0] code;
            logic corrected;
            logic uncorrectable;
        } result_t;

        wire run = i_rstb === 1'b1;
        wire reset_b = i_rstb !== 1'b0;
        wire flushing;
        wire flush_seen;
        wire flush_done;
        wire [B-1:0] acknowledged;
        logic [B-1:0] acknowledged_next;
        logic flushing_next;
        logic flush_done_next;
        wire flush_start = run && i_flush === 1'b1 && !flush_seen && !flushing && !flush_done;
        wire cancel = flushing || i_flush !== 1'b0 || flush_done;
        wire active = run && !cancel;
        wire [PERMISSION_WIDTH-1:0] read_permission;
        wire [PERMISSION_WIDTH-1:0] write_permission;
        logic [PERMISSION_WIDTH-1:0] read_permission_next;
        logic [PERMISSION_WIDTH-1:0] write_permission_next;
        wire [C-1:0] request_accept;
        wire [C-1:0] response_accept;
        wire [C-1:0] denied;
        wire [C-1:0] request_events;
        wire [C-1:0] response_events;
        wire [C-1:0] denied_events;
        wire [B-1:0] conflict_events;
        wire permission_event;
        wire [B-1:0] conflict;
        wire [B-1:0] request_pending;
        wire [B-1:0] request_fault;
        wire [C-1:0] collector_fault;
        wire [CLIENT_SLOT_WIDTH-1:0] issue [C];
        wire [CLIENT_SLOT_WIDTH-1:0] retire [C];
        wire [CLIENT_OCCUPANCY_WIDTH-1:0] occupancy [C];
        wire [N-1:0] allocated [C];
        wire [N-1:0] present [C];
        wire [$bits(metadata_t)-1:0] metadata [C][N];
        wire [$bits(result_t)-1:0] results [C][N];
        logic [MEM_ERROR_WIDTH-1:0] local_error [C];
        logic [BANK_INDEX_WIDTH-1:0] mapped_bank [C];
        logic [BANK_ADDR_WIDTH-1:0] mapped_address [C];
        logic [DATA_BYTES:0] transfer_bytes [C];
        logic permitted [C];
        logic [C-1:0] candidates [B];
        wire [C-1:0] request_grant [B];
        wire request_valid [B];
        wire [CLIENT_INDEX_WIDTH-1:0] selected_client [B];
        logic [CTRL_ERROR_WIDTH-1:0] response_error [B];
        logic response_target [B];
        logic [CLIENT_INDEX_WIDTH-1:0] response_client [B];
        logic [CLIENT_SLOT_WIDTH-1:0] response_slot [B];
        logic [B-1:0] response_candidates [C];
        wire collector_valid [C];
        wire [BANK_INDEX_WIDTH-1:0] selected_bank [C];
        wire [B-1:0] collector_grant [C];
        logic [C-1:0] collecting;
        logic [CLIENT_SLOT_WIDTH-1:0] collection_slot [C];
        result_t collection_result [C];
        logic any_occupied;
        logic [CTRL_ERROR_WIDTH-1:0] new_error;
        wire [CTRL_ERROR_WIDTH-1:0] sticky_error;
        wire banks_idle = (&i_bank_idle) === 1'b1;
        wire quiescent = !any_occupied && banks_idle && !(|request_pending) && !cancel;
        wire permission_accept = o_perm_ready && i_perm_valid === 1'b1;
        wire issue_enable = active && !o_error && !permission_accept;

        // All acknowledgement bits are remembered, including same-edge acks at
        // launch. A held flush request creates one transaction, not repeated ones.
        always_comb begin
            acknowledged_next = flush_start ? '0 : acknowledged;
            flushing_next = flushing;
            flush_done_next = 1'b0;

            for (int b = 0; b < B; b++) begin
                o_bank_flush[b] = run && (flush_start || flushing) &&
                    (flush_start || !acknowledged[b]);

                if (o_bank_flush[b] && i_bank_flush_completed[b] === 1'b1)
                    acknowledged_next[b] = 1'b1;
            end

            if (flush_start || flushing) begin
                flushing_next = !(&acknowledged_next);
                flush_done_next = &acknowledged_next;
            end
        end

        dff #(.WIDTH(B), .ASYNC_RESET(ASYNC_RESET)) u_acknowledged (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (flush_start || flushing)),
            .i_d(acknowledged_next),
            .o_q(acknowledged)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_flushing (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (flush_start || flushing)),
            .i_d(flushing_next),
            .o_q(flushing)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_flush_seen (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && ((i_flush === 1'b1 && !flush_seen) ||
                (i_flush === 1'b0 && flush_seen))),
            .i_d(i_flush === 1'b1),
            .o_q(flush_seen)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_flush_done (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (flush_start || flushing || flush_done)),
            .i_d(flush_done_next),
            .o_q(flush_done)
        );

        assign o_flushing = run && (flush_start || flushing);
        assign o_flush_completed = run && flush_done;

        always_comb begin
            any_occupied = 1'b0;

            for (int c = 0; c < C; c++) any_occupied |= |occupancy[c];

            for (int p = 0; p < PERMISSION_WIDTH; p++) begin
                read_permission_next[p] = i_read_permission[p] === 1'b1;
                write_permission_next[p] = i_write_permission[p] === 1'b1;
            end
        end

        assign o_busy = run && (any_occupied || o_flushing);
        assign o_idle = active && quiescent && !o_error;
        assign o_perm_ready = ENFORCE_PERMISSIONS == 1 && o_idle;

        dff #(.WIDTH(PERMISSION_WIDTH), .RESET_VALUE({PERMISSION_WIDTH{DEFAULT_ALLOW == 1}}),
            .ASYNC_RESET(ASYNC_RESET)) u_read_permission (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(permission_accept),
            .i_d(read_permission_next),
            .o_q(read_permission)
        );

        dff #(.WIDTH(PERMISSION_WIDTH), .RESET_VALUE({PERMISSION_WIDTH{DEFAULT_ALLOW == 1}}),
            .ASYNC_RESET(ASYNC_RESET)) u_write_permission (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(permission_accept),
            .i_d(write_permission_next),
            .o_q(write_permission)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_permission_event (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && permission_accept != permission_event),
            .i_d(permission_accept), .o_q(permission_event)
        );

        assign o_permission_updated = run && permission_event;
        assign o_request_accepted = run ? request_events : {C{1'b0}};
        assign o_response_accepted = run ? response_events : {C{1'b0}};
        assign o_permission_denied = run ? denied_events : {C{1'b0}};
        assign o_bank_conflict = run ? conflict_events : {B{1'b0}};

        // Mapping operands are constant geometry. Reject before using an address,
        // size or strobe as an index/shift; inactive paths stay at zero.
        always_comb begin
            for (int c = 0; c < C; c++) begin
                logic [63:0] address;
                logic [63:0] block_index;
                logic [63:0] bank_block;
                logic [63:0] raw_bank;
                logic [63:0] size;
                logic [DATA_BYTES-1:0] strobe;
                address = 64'(i_client_req_address[c*GLOBAL_ADDR_WIDTH+:GLOBAL_ADDR_WIDTH]);
                block_index = 0;
                bank_block = 0;
                raw_bank = 0;
                size = 0;
                strobe = i_client_req_wstrobe[c*DATA_BYTES+:DATA_BYTES];
                mapped_bank[c] = '0;
                mapped_address[c] = '0;
                transfer_bytes[c] = '0;
                permitted[c] = 1'b0;
                local_error[c] = MEM_ERR_NONE;

                if (i_client_req_valid[c] === 1'b1) begin
                    if ((^{i_client_req_write[c],
                        i_client_req_address[c*GLOBAL_ADDR_WIDTH+:GLOBAL_ADDR_WIDTH],
                        i_client_req_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH],
                        i_client_req_tag[c*T+:T]} === 1'bx) ||
                        (i_client_req_write[c] === 1'b1 && ^strobe === 1'bx))
                        local_error[c] = MEM_ERR_UNKNOWN_CONTROL;
                    else if (address >= TOTAL_CAPACITY_BYTES)
                        local_error[c] = MEM_ERR_ADDRESS_RANGE;
                    else if (i_client_req_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH] >
                        SIZE_WIDTH'($clog2(DATA_BYTES))) local_error[c] = MEM_ERR_SIZE;
                    else begin
                        size = 64'd1 << i_client_req_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH];
                        transfer_bytes[c] = (DATA_BYTES + 1)'(size);

                        if (address % DATA_BYTES + size > DATA_BYTES)
                            local_error[c] = MEM_ERR_WORD_CROSSING;
                        else if (address % size != 0) local_error[c] = MEM_ERR_ALIGNMENT;
                        else if (i_client_req_write[c] && (strobe >> size) != '0)
                            local_error[c] = MEM_ERR_STROBE;
                    end

                    if (local_error[c] == MEM_ERR_NONE) begin
                        block_index = address / STRIPE;
                        raw_bank = block_index % B;
                        bank_block = block_index / B;

                        if (MAP_MODE == MAP_XOR_STRIPED) raw_bank ^= bank_block % B;

                        mapped_bank[c] = BANK_INDEX_WIDTH'(raw_bank);
                        mapped_address[c] = BANK_ADDR_WIDTH'(bank_block * STRIPE +
                            address % STRIPE);
                        permitted[c] = ENFORCE_PERMISSIONS == 0 ||
                            (i_client_req_write[c] ?
                            write_permission[c*B+32'(raw_bank)] === 1'b1 :
                            read_permission[c*B+32'(raw_bank)] === 1'b1);

                        if (!permitted[c]) local_error[c] = MEM_ERR_PERMISSION;
                    end
                end
            end

            for (int b = 0; b < B; b++) begin
                candidates[b] = '0;

                for (int c = 0; c < C; c++) begin
                    candidates[b][c] = issue_enable && i_client_req_valid[c] === 1'b1 &&
                        local_error[c] == MEM_ERR_NONE && occupancy[c] < N &&
                        mapped_bank[c] == BANK_INDEX_WIDTH'(b);
                end
            end
        end

        for (genvar b = 0; b < B; b++) begin : g_request_arbiter
            wire accepted = o_bank_req_valid[b] && i_bank_req_ready[b] === 1'b1;

            round_robin_arbiter #(
                .NUM_REQUESTERS(C),
                .HAS_LOCK(0),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_arbiter (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_request(candidates[b]),
                .i_eligible({C{1'b1}}),
                .i_lock({C{1'b0}}),
                .i_accept(accepted),
                .i_flush(cancel || o_error),
                .o_grant_valid(request_valid[b]),
                .o_grant_onehot(request_grant[b]),
                .o_grant_index(selected_client[b]),
                .o_grant_lock(),
                .o_grant_accepted(),
                .o_contended(conflict[b]),
                .o_pending(request_pending[b]),
                .o_locked(),
                .o_lock_owner(),
                .o_protocol_error(request_fault[b])
            );
        end

        always_comb begin
            o_bank_req_valid = '0;
            o_bank_req_write = '0;
            o_bank_req_address = '0;
            o_bank_req_size_log2 = '0;
            o_bank_req_wdata = '0;
            o_bank_req_wstrobe = '0;
            o_bank_req_tag = '0;
            o_client_req_ready = '0;

            for (int c = 0; c < C; c++) begin
                if (issue_enable && occupancy[c] < N && i_client_req_valid[c] === 1'b1 &&
                    local_error[c] != MEM_ERR_NONE) o_client_req_ready[c] = 1'b1;
            end

            for (int b = 0; b < B; b++) begin
                if (issue_enable && request_valid[b] === 1'b1) begin
                    o_bank_req_valid[b] = 1'b1;
                    o_bank_req_write[b] = i_client_req_write[selected_client[b]];
                    o_bank_req_address[b*BANK_ADDR_WIDTH+:BANK_ADDR_WIDTH] =
                        mapped_address[selected_client[b]];
                    o_bank_req_size_log2[b*SIZE_WIDTH+:SIZE_WIDTH] =
                        i_client_req_size_log2[selected_client[b]*SIZE_WIDTH+:SIZE_WIDTH];
                    o_bank_req_tag[b*BANK_TAG_WIDTH+:BANK_TAG_WIDTH] =
                        {selected_client[b], issue[selected_client[b]]};

                    if (i_client_req_write[selected_client[b]]) begin
                        o_bank_req_wstrobe[b*DATA_BYTES+:DATA_BYTES] =
                            i_client_req_wstrobe[selected_client[b]*DATA_BYTES+:DATA_BYTES];

                        for (int byte_index = 0; byte_index < DATA_BYTES; byte_index++) begin
                            if (o_bank_req_wstrobe[b*DATA_BYTES+byte_index])
                                o_bank_req_wdata[b*D+byte_index*8+:8] =
                                    i_client_req_wdata[selected_client[b]*D+byte_index*8+:8];
                        end
                    end

                    o_client_req_ready[selected_client[b]] = i_bank_req_ready[b] === 1'b1;
                end
            end
        end

        // Identify a writable slot separately from validation. Malformed responses
        // with a recognizable obligation still enter its one-writer collector.
        always_comb begin
            for (int b = 0; b < B; b++) begin
                logic [BANK_TAG_WIDTH-1:0] tag;
                metadata_t saved;
                logic [scratchpad_bank_pkg::BANK_ERROR_WIDTH-1:0] code;
                tag = i_bank_rsp_tag[b*BANK_TAG_WIDTH+:BANK_TAG_WIDTH];
                code = i_bank_rsp_error_code[b*scratchpad_bank_pkg::BANK_ERROR_WIDTH+:
                    scratchpad_bank_pkg::BANK_ERROR_WIDTH];
                saved = '0;
                response_error[b] = CTRL_ERR_NONE;
                response_target[b] = 1'b0;
                response_client[b] = '0;
                response_slot[b] = '0;

                if (i_bank_rsp_valid[b] === 1'b1) begin
                    if (^tag === 1'bx) response_error[b] = CTRL_ERR_UNKNOWN_TAG;
                    else begin
                        response_client[b] = tag[BANK_TAG_WIDTH-1:CLIENT_SLOT_WIDTH];
                        response_slot[b] = tag[CLIENT_SLOT_WIDTH-1:0];

                        if (32'(response_client[b]) >= C) response_error[b] = CTRL_ERR_CLIENT;
                        else if (32'(response_slot[b]) >= N) response_error[b] = CTRL_ERR_SLOT;
                        else if (!allocated[response_client[b]][response_slot[b]])
                            response_error[b] = CTRL_ERR_UNALLOCATED;
                        else if (present[response_client[b]][response_slot[b]])
                            response_error[b] = CTRL_ERR_DUPLICATE;
                        else begin
                            response_target[b] = 1'b1;
                            saved = metadata[response_client[b]][response_slot[b]];

                            if (saved.bank != BANK_INDEX_WIDTH'(b))
                                response_error[b] = CTRL_ERR_BANK;
                            else if (i_bank_rsp_write[b] !== saved.write)
                                response_error[b] = CTRL_ERR_OPERATION;
                            else if ((^{i_bank_rsp_error[b], code, i_bank_rsp_corrected[b],
                                i_bank_rsp_uncorrectable[b]} === 1'bx) ||
                                code > scratchpad_bank_pkg::BANK_ERR_INTERNAL_PROTOCOL ||
                                (i_bank_rsp_corrected[b] && i_bank_rsp_uncorrectable[b]) ||
                                (i_bank_rsp_error[b] != (code != 0)) ||
                                (i_bank_rsp_uncorrectable[b] && !i_bank_rsp_error[b]))
                                response_error[b] = CTRL_ERR_STATUS;
                        end
                    end
                end
            end

            for (int c = 0; c < C; c++) begin
                response_candidates[c] = '0;

                for (int b = 0; b < B; b++) begin
                    response_candidates[c][b] = active && response_target[b] &&
                        response_client[b] == CLIENT_INDEX_WIDTH'(c);
                end
            end
        end

        for (genvar c = 0; c < C; c++) begin : g_collector
            round_robin_arbiter #(
                .NUM_REQUESTERS(B),
                .HAS_LOCK(0),
                .HOLD_PENDING(0),
                .ASYNC_RESET(ASYNC_RESET)) u_arbiter (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_request(response_candidates[c]),
                .i_eligible({B{1'b1}}),
                .i_lock({B{1'b0}}),
                .i_accept(active && collector_valid[c] === 1'b1),
                .i_flush(cancel),
                .o_grant_valid(collector_valid[c]),
                .o_grant_onehot(collector_grant[c]),
                .o_grant_index(selected_bank[c]),
                .o_grant_lock(),
                .o_grant_accepted(),
                .o_contended(),
                .o_pending(),
                .o_locked(),
                .o_lock_owner(),
                .o_protocol_error(collector_fault[c])
            );
        end

        always_comb begin
            o_bank_rsp_ready = '0;
            collecting = '0;

            for (int c = 0; c < C; c++) begin
                result_t result;
                result = '0;
                collection_slot[c] = '0;

                if (active && collector_valid[c] === 1'b1) begin
                    collecting[c] = 1'b1;
                    collection_slot[c] = response_slot[selected_bank[c]];
                    o_bank_rsp_ready[selected_bank[c]] = 1'b1;

                    if (response_error[selected_bank[c]] != CTRL_ERR_NONE) begin
                        result.error = 1'b1;
                        result.code = MEM_ERR_INTERNAL_PROTOCOL;
                        result.uncorrectable = 1'b1;
                    end else begin
                        result.data = i_bank_rsp_rdata[selected_bank[c]*D+:D];
                        result.error = i_bank_rsp_error[selected_bank[c]];
                        result.code = i_bank_rsp_error_code[
                            selected_bank[c]*MEM_ERROR_WIDTH+:MEM_ERROR_WIDTH];
                        result.corrected = i_bank_rsp_corrected[selected_bank[c]];
                        result.uncorrectable = i_bank_rsp_uncorrectable[selected_bank[c]];
                    end
                end
                collection_result[c] = result;
            end

            // Untargetable malformed responses have no table write and may drain
            // concurrently with collectors without violating the one-writer rule.
            for (int b = 0; b < B; b++) begin
                if (active && i_bank_rsp_valid[b] === 1'b1 && !response_target[b])
                    o_bank_rsp_ready[b] = 1'b1;
            end
        end

        always_comb begin
            new_error = CTRL_ERR_NONE;

            for (int b = 0; b < B; b++) begin
                if (o_bank_rsp_ready[b] && i_bank_rsp_valid[b] === 1'b1 &&
                    response_error[b] != CTRL_ERR_NONE && new_error == CTRL_ERR_NONE)
                    new_error = response_error[b];
            end

            if (active && ((|request_fault) || (|collector_fault)) && new_error == CTRL_ERR_NONE)
                new_error = CTRL_ERR_ARBITER;
        end

        dff #(.WIDTH(CTRL_ERROR_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_sticky_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && ((!o_error && new_error != CTRL_ERR_NONE) ||
                (quiescent && i_error_clear === 1'b1 && new_error == CTRL_ERR_NONE))),
            .i_d(new_error),
            .o_q(sticky_error)
        );

        assign o_error = run && sticky_error != CTRL_ERR_NONE;
        assign o_error_code = run ? sticky_error : {CTRL_ERROR_WIDTH{1'b0}};

        for (genvar c = 0; c < C; c++) begin : g_client
            wire allocate_slot = request_accept[c];
            wire retire_slot = response_accept[c];
            wire clear_slots = run && (flushing || flush_done || i_flush === 1'b1);
            wire [CLIENT_SLOT_WIDTH-1:0] issue_next = issue[c] == CLIENT_SLOT_WIDTH'(N - 1) ?
                '0 : issue[c] + 1'b1;
            wire [CLIENT_SLOT_WIDTH-1:0] retire_next = retire[c] == CLIENT_SLOT_WIDTH'(N - 1) ?
                '0 : retire[c] + 1'b1;
            wire [CLIENT_OCCUPANCY_WIDTH-1:0] occupancy_next =
                occupancy[c] + CLIENT_OCCUPANCY_WIDTH'(allocate_slot) -
                CLIENT_OCCUPANCY_WIDTH'(retire_slot);
            metadata_t head_metadata;
            result_t head_result;
            metadata_t allocation_metadata;
            result_t local_result;

            assign request_accept[c] = o_client_req_ready[c] && i_client_req_valid[c] === 1'b1;
            assign response_accept[c] = o_client_rsp_valid[c] && i_client_rsp_ready[c] === 1'b1;
            assign denied[c] = request_accept[c] && local_error[c] == MEM_ERR_PERMISSION;
            assign o_client_outstanding[c*CLIENT_OCCUPANCY_WIDTH+:CLIENT_OCCUPANCY_WIDTH] =
                run ? occupancy[c] : {CLIENT_OCCUPANCY_WIDTH{1'b0}};

            always_comb begin
                allocation_metadata.tag = ^i_client_req_tag[c*T+:T] === 1'bx ?
                    '0 : i_client_req_tag[c*T+:T];
                allocation_metadata.write = i_client_req_write[c] === 1'b1;
                allocation_metadata.bank = mapped_bank[c];
                local_result = '0;
                local_result.error = 1'b1;
                local_result.code = local_error[c];
                head_metadata = '0;
                head_result = '0;
                o_client_rsp_valid[c] = 1'b0;

                if (active && allocated[c][retire[c]] && present[c][retire[c]]) begin
                    head_metadata = metadata[c][retire[c]];
                    head_result = results[c][retire[c]];
                    o_client_rsp_valid[c] = 1'b1;
                end

                o_client_rsp_write[c] = head_metadata.write;
                o_client_rsp_tag[c*T+:T] = head_metadata.tag;
                o_client_rsp_rdata[c*D+:D] = head_result.data;
                o_client_rsp_error[c] = head_result.error;
                o_client_rsp_error_code[c*MEM_ERROR_WIDTH+:MEM_ERROR_WIDTH] = head_result.code;
                o_client_rsp_corrected[c] = head_result.corrected;
                o_client_rsp_uncorrectable[c] = head_result.uncorrectable;
            end

            dff #(.WIDTH(CLIENT_SLOT_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_issue (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(clear_slots || allocate_slot),
                .i_d(clear_slots ? {CLIENT_SLOT_WIDTH{1'b0}} : issue_next),
                .o_q(issue[c])
            );

            dff #(.WIDTH(CLIENT_SLOT_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_retire (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(clear_slots || retire_slot),
                .i_d(clear_slots ? {CLIENT_SLOT_WIDTH{1'b0}} : retire_next),
                .o_q(retire[c])
            );

            dff #(.WIDTH(CLIENT_OCCUPANCY_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_occupancy (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(clear_slots || (allocate_slot != retire_slot)),
                .i_d(clear_slots ? {CLIENT_OCCUPANCY_WIDTH{1'b0}} : occupancy_next),
                .o_q(occupancy[c])
            );

            for (genvar s = 0; s < N; s++) begin : g_slot
                wire allocating = allocate_slot && issue[c] == CLIENT_SLOT_WIDTH'(s);
                wire retiring = retire_slot && retire[c] == CLIENT_SLOT_WIDTH'(s);
                wire collecting_slot = collecting[c] &&
                    collection_slot[c] == CLIENT_SLOT_WIDTH'(s);
                wire local_completion = allocating && local_error[c] != MEM_ERR_NONE;

                dff #(.ASYNC_RESET(ASYNC_RESET)) u_allocated (
                    .i_clk(i_clk),
                    .i_rstb(reset_b),
                    .i_enable(clear_slots || allocating || retiring),
                    .i_d(!clear_slots && allocating),
                    .o_q(allocated[c][s])
                );

                dff #(.ASYNC_RESET(ASYNC_RESET)) u_present (
                    .i_clk(i_clk),
                    .i_rstb(reset_b),
                    .i_enable(clear_slots || allocating || retiring || collecting_slot),
                    .i_d(!clear_slots && (local_completion || collecting_slot)),
                    .o_q(present[c][s])
                );

                // Payload has no reset; validity is the sole authority to expose it.
                dff #(.WIDTH($bits(metadata_t))) u_metadata (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(allocating),
                    .i_d(allocation_metadata),
                    .o_q(metadata[c][s])
                );

                dff #(.WIDTH($bits(result_t))) u_result (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(local_completion || collecting_slot),
                    .i_d(local_completion ? local_result : collection_result[c]),
                    .o_q(results[c][s])
                );
            end
        end

        // Events describe the preceding active edge and can be high on successive
        // cycles when the corresponding action happens on successive edges.
        dff #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET)) u_request_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && request_accept != request_events),
            .i_d(request_accept),
            .o_q(request_events)
        );

        dff #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET)) u_response_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && response_accept != response_events),
            .i_d(response_accept),
            .o_q(response_events)
        );

        dff #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET)) u_denied_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && denied != denied_events),
            .i_d(denied),
            .o_q(denied_events)
        );

        dff #(.WIDTH(B), .ASYNC_RESET(ASYNC_RESET)) u_conflict_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && conflict_events != (issue_enable ? conflict : {B{1'b0}})),
            .i_d(issue_enable ? conflict : {B{1'b0}}),
            .o_q(conflict_events)
        );

`ifdef MOSAIC_SCRATCHPAD_CONTROLLER_INSTRUMENTATION
        // Verification-only adapter exercises the same optional counter module
        // that integration may bind. Production controller state is unaffected.
        localparam int COUNTER_COUNT = C * 15 + B * 10 + C * B + 2;
        logic [COUNTER_COUNT*8-1:0] counter_increments;
        logic [C*8-1:0] counter_occupancy;

        always_comb begin
            counter_increments = '0;
            counter_occupancy = '0;

            for (int c = 0; c < C; c++) begin
                int bank;
                int contenders;
                logic [7:0] read_bytes;
                logic [7:0] write_bytes;
                bank = 32'(mapped_bank[c]);
                contenders = 0;
                read_bytes = '0;
                write_bytes = '0;

                for (int b = 0; b < B; b++) contenders += int'(response_candidates[c][b]);

                if (request_accept[c] && local_error[c] == MEM_ERR_NONE) begin
                    if (!i_client_req_write[c]) read_bytes = 8'(transfer_bytes[c]);
                    else begin
                        for (int k = 0; k < DATA_BYTES; k++)
                            write_bytes += 8'(i_client_req_wstrobe[c*DATA_BYTES+k]);
                    end
                end

                counter_occupancy[c*8+:8] = 8'(occupancy[c]);
                counter_increments[(c*15)*8+:8] = 8'(request_accept[c]);
                counter_increments[(c*15+1)*8+:8] = 8'(response_accept[c]);
                counter_increments[(c*15+2)*8+:8] = read_bytes;
                counter_increments[(c*15+3)*8+:8] = write_bytes;
                counter_increments[(c*15+4)*8+:8] =
                    8'(candidates[bank][c] && !request_accept[c]);
                counter_increments[(c*15+5)*8+:8] =
                    8'(issue_enable && i_client_req_valid[c] === 1'b1 && occupancy[c] == N);
                counter_increments[(c*15+6)*8+:8] =
                    8'(o_client_rsp_valid[c] && i_client_rsp_ready[c] !== 1'b1);
                counter_increments[(c*15+7)*8+:8] = 8'(contenders > 1);
                counter_increments[(c*15+8)*8+:8] = 8'(denied[c]);

                for (int code = 1; code <= 6; code++)
                    counter_increments[(c*15+8+code)*8+:8] =
                        8'(request_accept[c] && local_error[c] == MEM_ERROR_WIDTH'(code));

                for (int b = 0; b < B; b++)
                    counter_increments[(C*15+B*10+c*B+b)*8+:8] =
                        8'(denied[c] && mapped_bank[c] == BANK_INDEX_WIDTH'(b));
            end

            for (int b = 0; b < B; b++) begin
                logic accepted;
                int contenders;
                logic [7:0] write_bytes;
                accepted = o_bank_req_valid[b] && i_bank_req_ready[b] === 1'b1;
                contenders = 0;
                write_bytes = '0;

                for (int c = 0; c < C; c++) contenders += int'(candidates[b][c]);

                for (int k = 0; k < DATA_BYTES; k++)
                    write_bytes += 8'(o_bank_req_wstrobe[b*DATA_BYTES+k]);

                counter_increments[(C*15+b*10)*8+:8] = 8'(accepted && !o_bank_req_write[b]);
                counter_increments[(C*15+b*10+1)*8+:8] = 8'(accepted && o_bank_req_write[b]);

                if (accepted && !o_bank_req_write[b])
                    counter_increments[(C*15+b*10+2)*8+:8] =
                        8'(64'd1 << o_bank_req_size_log2[b*SIZE_WIDTH+:SIZE_WIDTH]);

                if (accepted && o_bank_req_write[b])
                    counter_increments[(C*15+b*10+3)*8+:8] = write_bytes;
                counter_increments[(C*15+b*10+4)*8+:8] = 8'(issue_enable && conflict[b]);
                counter_increments[(C*15+b*10+5)*8+:8] = 8'(contenders > int'(accepted));
                counter_increments[(C*15+b*10+6)*8+:8] =
                    8'(o_bank_req_valid[b] && !accepted);
                counter_increments[(C*15+b*10+7)*8+:8] =
                    8'(active && i_bank_rsp_valid[b] === 1'b1 && !o_bank_rsp_ready[b]);

                if (o_bank_rsp_ready[b] && i_bank_rsp_valid[b] === 1'b1 &&
                    response_error[b] == CTRL_ERR_NONE) begin
                    counter_increments[(C*15+b*10+8)*8+:8] = 8'(i_bank_rsp_corrected[b]);
                    counter_increments[(C*15+b*10+9)*8+:8] = 8'(i_bank_rsp_uncorrectable[b]);
                end
            end

            counter_increments[(COUNTER_COUNT-2)*8+:8] = 8'(flush_start);
            counter_increments[(COUNTER_COUNT-1)*8+:8] = 8'(o_flushing);
        end

        scratchpad_controller_instrumentation #(
            .C(C), .B(B), .ASYNC_RESET(ASYNC_RESET)
        ) u_instrumentation (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_increments(counter_increments),
                .i_occupancy(counter_occupancy)
            );
`endif
    end
endmodule
`default_nettype wire
