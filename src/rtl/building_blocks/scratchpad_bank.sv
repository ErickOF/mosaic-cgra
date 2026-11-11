`timescale 1ns / 1ps
`default_nettype none

// Byte-addressed ordered bank over a replaceable 1RW SRAM protocol wrapper.
// SECDED reads reserve the backend until classification/scrub; protected partial
// writes reserve it through commit. No storage data or protection bit is reset.
module scratchpad_bank #(
    parameter DATA_WIDTH = 128,
    parameter DEPTH_WORDS = 1024,
    parameter TAG_WIDTH = 8,
    parameter MAX_OUTSTANDING = 8,
    parameter BACKEND_READ_LATENCY = 1,
    parameter PROTECTION_MODE = 0,
    parameter PARITY_GRANULARITY = 8,
    parameter SCRUB_ON_CORRECT = 1,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 8) === 1'b1) && (((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((((DATA_WIDTH / 8) & ((DATA_WIDTH / 8) - 1)) == 0) === 1'b1) &&
        ((DEPTH_WORDS >= 1) === 1'b1) && (((^DEPTH_WORDS == 1'b0) || (^DEPTH_WORDS == 1'b1)) === 1'b1) &&
        ((TAG_WIDTH >= 1) === 1'b1) && (((^TAG_WIDTH == 1'b0) || (^TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((MAX_OUTSTANDING >= 1) === 1'b1) && (((^MAX_OUTSTANDING == 1'b0) || (^MAX_OUTSTANDING == 1'b1)) === 1'b1) &&
        ((BACKEND_READ_LATENCY >= 1) === 1'b1) && (((^BACKEND_READ_LATENCY == 1'b0) || (^BACKEND_READ_LATENCY == 1'b1)) === 1'b1) &&
        ((MAX_OUTSTANDING >= BACKEND_READ_LATENCY) === 1'b1) &&
        ((PROTECTION_MODE === 0) || (PROTECTION_MODE === 1) || (PROTECTION_MODE === 2)) &&
        ((PROTECTION_MODE != 2 || DATA_WIDTH <= 256) === 1'b1) &&
        ((PARITY_GRANULARITY >= 8) === 1'b1) && (((^PARITY_GRANULARITY == 1'b0) || (^PARITY_GRANULARITY == 1'b1)) === 1'b1) &&
        ((PARITY_GRANULARITY % 8 == 0) === 1'b1) &&
        ((DATA_WIDTH % (PARITY_GRANULARITY > 0 ? PARITY_GRANULARITY : 1) == 0) === 1'b1) &&
        ((SCRUB_ON_CORRECT === 0) || (SCRUB_ON_CORRECT === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((128'(DEPTH_WORDS) * 128'(DATA_WIDTH) < 128'd2147483647) === 1'b1) &&
        ((128'(MAX_OUTSTANDING) * (128'(DATA_WIDTH) + 128'(TAG_WIDTH) + 128) <
            128'd2147483647) === 1'b1) &&
        ((128'(BACKEND_READ_LATENCY) + 128'(TAG_WIDTH) + 128'(DATA_WIDTH) <
            128'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 8,
    localparam int WORDS = PARAMETERS_VALID ? DEPTH_WORDS : 1,
    localparam int T = PARAMETERS_VALID ? TAG_WIDTH : 1,
    localparam int N = PARAMETERS_VALID ? MAX_OUTSTANDING : 1,
    localparam int LATENCY = PARAMETERS_VALID ? BACKEND_READ_LATENCY : 1,
    localparam int G = PARAMETERS_VALID ? PARITY_GRANULARITY : 8,
    localparam int DATA_BYTES = D / 8,
    localparam int WORD_ADDR_WIDTH = WORDS > 1 ? $clog2(WORDS) : 1,
    localparam int BYTE_LOG2 = $clog2(DATA_BYTES),
    localparam int BYTE_OFFSET_WIDTH = DATA_BYTES > 1 ? BYTE_LOG2 : 1,
    localparam logic [63:0] CAPACITY_BYTES = 64'(WORDS) * 64'(DATA_BYTES),
    localparam int BYTE_ADDR_WIDTH = CAPACITY_BYTES > 1 ? $clog2(CAPACITY_BYTES) : 1,
    localparam int SIZE_WIDTH = BYTE_LOG2 > 0 ? $clog2(BYTE_LOG2 + 1) : 1,
    localparam int SLOT_WIDTH = N > 1 ? $clog2(N) : 1,
    localparam int OCCUPANCY_WIDTH = $clog2(64'(N) + 1),
    localparam int PARITY_BITS = D / G
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_req_valid,
    output logic o_req_ready,
    input logic i_req_write,
    input logic [BYTE_ADDR_WIDTH-1:0] i_req_address,
    input logic [SIZE_WIDTH-1:0] i_req_size_log2,
    input logic [D-1:0] i_req_wdata,
    input logic [DATA_BYTES-1:0] i_req_wstrobe,
    input logic [T-1:0] i_req_tag,
    output logic o_rsp_valid,
    input logic i_rsp_ready,
    output logic o_rsp_write,
    output logic [D-1:0] o_rsp_rdata,
    output logic [T-1:0] o_rsp_tag,
    output logic o_rsp_error,
    output logic [scratchpad_bank_pkg::BANK_ERROR_WIDTH-1:0] o_rsp_error_code,
    output logic o_rsp_corrected,
    output logic o_rsp_uncorrectable,
    output logic o_idle,
    output logic o_busy,
    output logic [OCCUPANCY_WIDTH-1:0] o_outstanding,
    output logic o_request_accepted,
    output logic o_read_accepted,
    output logic o_write_accepted,
    output logic o_response_accepted,
    output logic o_corrected_event,
    output logic o_uncorrectable_event,
    output logic o_scrub_completed,
    output logic o_flush_completed,
    output logic o_error,
    output logic [scratchpad_bank_pkg::BANK_ERROR_WIDTH-1:0] o_error_code
);
    import scratchpad_bank_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        scratchpad_bank_parameters_must_be_valid invalid_parameters ();
    end else begin : g_bank
        localparam int HAMMING_BITS = ecc_pkg::hamming_bits(D);
        localparam int ECC_WIDTH = D + HAMMING_BITS + 1;
        localparam int STORED_WIDTH = PROTECTION_MODE == PROTECT_NONE ? D :
            PROTECTION_MODE == PROTECT_PARITY ? D + PARITY_BITS : ECC_WIDTH;
        localparam int GRANULE = PROTECTION_MODE == PROTECT_NONE ? 8 : 1;
        localparam int MASK_WIDTH = STORED_WIDTH / GRANULE;

        // Metadata/result widths depend on the public geometry.
        typedef struct packed {
            logic [T-1:0] tag;
            logic write;
            logic [WORD_ADDR_WIDTH-1:0] address;
            logic [BYTE_OFFSET_WIDTH-1:0] offset;
            logic [SIZE_WIDTH-1:0] size;
        } metadata_t;

        typedef struct packed {
            logic [D-1:0] data;
            logic error;
            logic [BANK_ERROR_WIDTH-1:0] code;
            logic corrected;
            logic uncorrectable;
        } result_t;

        wire run = i_rstb === 1'b1;
        wire reset_b = i_rstb !== 1'b0;
        wire normal = run && i_flush === 1'b0;
        wire flushing = run && i_flush === 1'b1;
        wire [SLOT_WIDTH-1:0] issue_pointer;
        wire [SLOT_WIDTH-1:0] retire_pointer;
        wire [N-1:0] allocated;
        wire [N-1:0] present;
        wire [N-1:0] awaiting;
        wire [N-1:0] allocate_select;
        wire [N-1:0] retire_select;
        wire [N-1:0] return_select;
        wire [N-1:0] return_write;
        wire [N-1:0] suppressed_return;
        wire unused_issue_valid;
        wire unused_retire_valid;
        wire return_tag_valid;
        wire [2:0] unused_occupancy_status;
        wire [7:0] events;
        wire [1:0] work_state;
        wire flush_seen;
        wire [SLOT_WIDTH-1:0] work_slot;
        wire [D-1:0] saved_data;
        wire [DATA_BYTES-1:0] saved_mask;
        wire [STORED_WIDTH-1:0] work_code;
        wire [MASK_WIDTH-1:0] work_mask;
        result_t work_result;
        metadata_t metadata [N];
        result_t results [N];
        metadata_t new_metadata;
        metadata_t returned_metadata;
        metadata_t head_metadata;
        metadata_t work_metadata;
        result_t local_result;
        result_t decoded_result;
        result_t head_result;
        bank_error_t request_error;
        logic [DATA_BYTES-1:0] requested_mask;
        logic [DATA_BYTES-1:0] shifted_mask;
        logic [D-1:0] shifted_data;
        logic partial_group;
        wire [WORD_ADDR_WIDTH-1:0] request_word =
            WORD_ADDR_WIDTH'(i_req_address >> BYTE_LOG2);
        wire [BYTE_OFFSET_WIDTH-1:0] request_offset =
            BYTE_OFFSET_WIDTH'(i_req_address & (DATA_BYTES - 1));
        wire offered = i_req_valid === 1'b1;
        wire capacity = o_outstanding < OCCUPANCY_WIDTH'(N);
        wire candidate = normal && !o_error && capacity && work_state === BANK_WORK_IDLE && offered;
        wire legal = request_error == BANK_ERR_NONE;
        wire write = i_req_write === 1'b1;
        wire nonzero_write = write && (|i_req_wstrobe);
        wire rmw = nonzero_write && (PROTECTION_MODE == PROTECT_SECDED ?
            !(request_offset == 0 && 32'(i_req_size_log2) == BYTE_LOG2 && (&i_req_wstrobe)) :
            PROTECTION_MODE == PROTECT_PARITY && partial_group);
        wire lock_request = rmw || (PROTECTION_MODE == PROTECT_SECDED && !write);
        wire needs_backend = legal && (!write || nonzero_write);
        wire backend_req_ready;
        wire backend_req_error;
        wire backend_rsp_valid;
        wire [STORED_WIDTH-1:0] backend_rsp_data;
        wire [SLOT_WIDTH-1:0] backend_rsp_tag;
        wire backend_busy;
        wire [OCCUPANCY_WIDTH-1:0] unused_backend_outstanding;
        wire backend_rsp_ready = normal;
        wire return_accept = normal && backend_rsp_valid === 1'b1;
        wire return_bad = return_accept && (!return_tag_valid ||
            allocated[backend_rsp_tag] !== 1'b1 || awaiting[backend_rsp_tag] !== 1'b1 ||
            present[backend_rsp_tag] !== 1'b0 ||
            (returned_metadata.write && !(work_state === BANK_WORK_WAIT &&
                backend_rsp_tag === work_slot)));
        wire return_ok = return_accept && !return_bad;
        wire return_lock = return_ok && work_state === BANK_WORK_WAIT &&
            backend_rsp_tag == work_slot;
        wire decode_good;
        wire decoded_corrected;
        wire [D-1:0] decoded_data;
        wire [STORED_WIDTH-1:0] repaired_code;
        wire needs_commit = return_lock && decode_good &&
            (returned_metadata.write || (decoded_corrected && SCRUB_ON_CORRECT == 1));
        wire commit_offer = normal && work_state === BANK_WORK_COMMIT;
        wire backend_req_valid = commit_offer || (candidate && needs_backend);
        wire backend_req_write = commit_offer || (write && !rmw);
        wire request_accept = offered && o_req_ready;
        wire backend_accept = backend_req_valid && backend_req_ready === 1'b1;
        wire commit = commit_offer && backend_req_ready === 1'b1;
        wire response_accept = o_rsp_valid && i_rsp_ready === 1'b1;
        wire immediate = request_accept && (request_error != BANK_ERR_NONE || !needs_backend ||
            (write && !rmw));
        wire complete_return = return_ok && !needs_commit;
        wire internal_bad = normal && (return_bad ||
            (backend_rsp_valid !== 1'b0 && backend_rsp_valid !== 1'b1) ||
            (backend_req_valid && (backend_req_error !== 1'b0 ||
                (backend_req_ready !== 1'b0 && backend_req_ready !== 1'b1))) ||
            (backend_accept && !(commit_offer || (request_accept && needs_backend))) ||
            (^o_outstanding === 1'bx) || $countones(allocated) != 32'(o_outstanding) ||
            (^allocated === 1'bx) || (^present === 1'bx) || (^awaiting === 1'bx) ||
            ((issue_pointer < N) !== 1'b1) || ((retire_pointer < N) !== 1'b1) ||
            !(work_state === BANK_WORK_IDLE || work_state === BANK_WORK_WAIT ||
                work_state === BANK_WORK_COMMIT));
        wire clear_error = normal && !o_busy && i_error_clear === 1'b1 && !internal_bad;
        wire [SLOT_WIDTH-1:0] next_issue = issue_pointer == SLOT_WIDTH'(N - 1) ?
            '0 : issue_pointer + 1'b1;
        wire [SLOT_WIDTH-1:0] next_retire = retire_pointer == SLOT_WIDTH'(N - 1) ?
            '0 : retire_pointer + 1'b1;
        wire [WORD_ADDR_WIDTH-1:0] backend_address = commit_offer ?
            work_metadata.address : request_word;
        wire [STORED_WIDTH-1:0] encoded_code;
        wire [D-1:0] encode_data;
        logic [D-1:0] merged_data;
        logic [MASK_WIDTH-1:0] generated_mask;
        wire [STORED_WIDTH-1:0] decode_code;
        wire [PARITY_BITS-1:0] parity_errors;
        wire encode_enable =
            (candidate && legal && write && nonzero_write && !rmw) ||
            (needs_commit && returned_metadata.write);
        wire [DATA_BYTES-1:0] encode_mask = needs_commit ? saved_mask : shifted_mask;
        wire [STORED_WIDTH-1:0] backend_write_data = commit_offer ?
            work_code : encoded_code;
        wire [MASK_WIDTH-1:0] backend_write_mask = commit_offer ? work_mask : generated_mask;
        wire corrected_event = return_ok && decoded_corrected;
        wire uncorrectable_event = return_ok && !decode_good;
        wire scrub_event = commit && !work_metadata.write;
        // Bindable request/error events and byte weights need no baseline counters.
        wire [5:0] illegal_events;
        wire [DATA_BYTES:0] read_bytes = request_accept && legal && !write ?
            (DATA_BYTES + 1)'(1 << i_req_size_log2) : '0;
        wire [DATA_BYTES:0] write_bytes = request_accept && legal && write ?
            (DATA_BYTES + 1)'($countones(i_req_wstrobe)) : '0;

        assign o_req_ready = normal && !o_error && capacity && work_state === BANK_WORK_IDLE &&
            (!needs_backend || backend_req_ready === 1'b1);
        assign o_rsp_valid = normal && allocated[retire_pointer] === 1'b1 &&
            present[retire_pointer] === 1'b1;
        assign o_busy = o_outstanding !== '0 || work_state !== BANK_WORK_IDLE ||
            backend_busy || flushing;
        assign o_idle = !o_busy && !o_error;
        assign o_error = o_error_code != BANK_ERR_NONE;
        assign {o_request_accepted, o_read_accepted, o_write_accepted, o_response_accepted,
            o_corrected_event, o_uncorrectable_event, o_scrub_completed, o_flush_completed} =
            run ? events : '0;
        assign head_metadata = metadata[retire_pointer];
        assign work_metadata = metadata[work_slot];
        assign head_result = results[retire_pointer];
        assign returned_metadata = return_tag_valid ? metadata[backend_rsp_tag] : '0;
        assign new_metadata = {(^i_req_tag === 1'bx) ? {T{1'b0}} : i_req_tag, write,
            request_word, request_offset, i_req_size_log2};
        assign local_result = {{D{1'b0}}, request_error != BANK_ERR_NONE,
            request_error, 1'b0, 1'b0};

        // Knownness precedes numeric checks. Crossing precedes alignment so a
        // crossing request is explicitly classified rather than silently split.
        always_comb begin
            request_error = BANK_ERR_NONE;
            requested_mask = '0;
            shifted_mask = '0;
            shifted_data = '0;
            partial_group = 1'b0;

            if (offered) begin
                if (^{i_req_write, i_req_address, i_req_size_log2, i_req_tag} === 1'bx ||
                    (write && ^i_req_wstrobe === 1'bx))
                    request_error = BANK_ERR_UNKNOWN_CONTROL;
                else if (64'(i_req_address) >= CAPACITY_BYTES)
                    request_error = BANK_ERR_ADDRESS_RANGE;
                else if (32'(i_req_size_log2) > BYTE_LOG2) request_error = BANK_ERR_SIZE;
                else if (32'(request_offset) + (32'd1 << i_req_size_log2) > DATA_BYTES)
                    request_error = BANK_ERR_WORD_CROSSING;
                else if ((i_req_address & ((32'd1 << i_req_size_log2) - 1)) != 0)
                    request_error = BANK_ERR_ALIGNMENT;
                else begin
                    for (int b = 0; b < DATA_BYTES; b++)
                        requested_mask[b] = b < (32'd1 << i_req_size_log2);

                    if (write && (i_req_wstrobe & ~requested_mask) != 0)
                        request_error = BANK_ERR_STROBE;
                end

                if (request_error == BANK_ERR_NONE && write) begin
                    shifted_mask = i_req_wstrobe << request_offset;

                    for (int b = 0; b < DATA_BYTES; b++) begin
                        if (i_req_wstrobe[b])
                            shifted_data |= D'(i_req_wdata[b*8+:8]) << (8 * (b + request_offset));
                    end

                    for (int g = 0; g < PARITY_BITS; g++) begin
                        if ((|shifted_mask[g*(G/8)+:(G/8)]) &&
                            !(&shifted_mask[g*(G/8)+:(G/8)])) partial_group = 1'b1;
                    end
                end
            end
        end

        decoder #(.NUM_OUTPUTS(N)) u_allocate (
            .i_enable(request_accept),
            .i_select(issue_pointer),
            .o_decoded(allocate_select),
            .o_select_valid(unused_issue_valid)
        );

        decoder #(.NUM_OUTPUTS(N)) u_retire (
            .i_enable(response_accept),
            .i_select(retire_pointer),
            .o_decoded(retire_select),
            .o_select_valid(unused_retire_valid)
        );

        decoder #(.NUM_OUTPUTS(N)) u_return (
            .i_enable(return_accept),
            .i_select(backend_rsp_tag),
            .o_decoded(return_select),
            .o_select_valid(return_tag_valid)
        );

        write_gate #(.WIDTH(N)) u_return_write (
            .i_write_enable(return_select),
            .i_suppress({N{return_bad}}),
            .o_write_enable(return_write),
            .o_write_suppressed(suppressed_return)
        );

        for (genvar n = 0; n < N; n++) begin : g_slot
            wire result_enable = (allocate_select[n] && immediate) ||
                (return_write[n] && complete_return) || (commit && work_slot == SLOT_WIDTH'(n));
            result_t result_input;
            assign result_input = allocate_select[n] ? local_result :
                commit && work_slot == SLOT_WIDTH'(n) ? work_result : decoded_result;

            dff #(.WIDTH($bits(metadata_t))) u_metadata (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(allocate_select[n]),
                .i_d(new_metadata),
                .o_q(metadata[n])
            );

            dff #(.WIDTH($bits(result_t))) u_result (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(result_enable),
                .i_d(result_input),
                .o_q(results[n])
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_allocated (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(flushing || allocate_select[n] || retire_select[n]),
                .i_d(!flushing && allocate_select[n]),
                .o_q(allocated[n])
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_present (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(flushing || allocate_select[n] || retire_select[n] || result_enable),
                .i_d(!flushing && result_enable),
                .o_q(present[n])
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_awaiting (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(flushing || allocate_select[n] || return_write[n]),
                .i_d(!flushing && allocate_select[n] && legal && needs_backend && (!write || rmw)),
                .o_q(awaiting[n])
            );
        end

        counter #(.WIDTH(OCCUPANCY_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(0)) u_count (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(request_accept ^ response_accept),
            .i_clear(flushing),
            .i_load(1'b0),
            .i_direction(response_accept),
            .i_load_value({OCCUPANCY_WIDTH{1'b0}}),
            .o_count(o_outstanding),
            .o_overflow(unused_occupancy_status[0]),
            .o_underflow(unused_occupancy_status[1]),
            .o_terminal(unused_occupancy_status[2])
        );

        dff #(.WIDTH(SLOT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_issue (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || request_accept),
            .i_d(flushing ? {SLOT_WIDTH{1'b0}} : next_issue),
            .o_q(issue_pointer)
        );

        dff #(.WIDTH(SLOT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_retire_pointer (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || response_accept),
            .i_d(flushing ? {SLOT_WIDTH{1'b0}} : next_retire),
            .o_q(retire_pointer)
        );

        dff #(.WIDTH(BANK_ERROR_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(clear_error || (internal_bad && !o_error)),
            .i_d(clear_error ? scratchpad_bank_pkg::BANK_ERR_NONE :
                scratchpad_bank_pkg::BANK_ERR_INTERNAL_PROTOCOL),
            .o_q(o_error_code)
        );

        // Lock ownership is established on acceptance, before a later correction
        // can schedule scrub. This prevents a younger write from being overwritten.
        dff #(.WIDTH(2), .ASYNC_RESET(ASYNC_RESET != 0)) u_work_state (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || (request_accept && legal && lock_request) ||
                return_lock || commit),
            .i_d(flushing || commit || (return_lock && !needs_commit) ?
                scratchpad_bank_pkg::BANK_WORK_IDLE : return_lock ?
                scratchpad_bank_pkg::BANK_WORK_COMMIT : scratchpad_bank_pkg::BANK_WORK_WAIT),
            .o_q(work_state)
        );

        dff #(.WIDTH(SLOT_WIDTH)) u_work_slot (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(request_accept && legal && lock_request),
            .i_d(issue_pointer),
            .o_q(work_slot)
        );

        dff #(.WIDTH(D + DATA_BYTES)) u_merge_operands (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(request_accept && legal && rmw),
            .i_d({shifted_data, shifted_mask}),
            .o_q({saved_data, saved_mask})
        );

        dff #(.WIDTH(STORED_WIDTH + MASK_WIDTH + $bits(result_t))) u_work_payload (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(needs_commit),
            .i_d({returned_metadata.write ? encoded_code : repaired_code,
                returned_metadata.write ? generated_mask : {MASK_WIDTH{1'b1}}, decoded_result}),
            .o_q({work_code, work_mask, work_result})
        );

        operand_isolation #(.WIDTH(STORED_WIDTH)) u_decode_isolation (
            .i_data(backend_rsp_data),
            .i_isolate(!return_ok),
            .o_data(decode_code)
        );

        always_comb begin
            merged_data = decoded_data;

            for (int b = 0; b < DATA_BYTES; b++) begin
                if (saved_mask[b]) merged_data[b*8+:8] = saved_data[b*8+:8];
            end

            generated_mask = '0;

            if (PROTECTION_MODE == PROTECT_NONE) generated_mask = MASK_WIDTH'(encode_mask);
            else if (PROTECTION_MODE == PROTECT_SECDED) generated_mask = '1;
            else begin
                for (int g = 0; g < PARITY_BITS; g++) begin
                    generated_mask[g*G+:G] = {G{|encode_mask[g*(G/8)+:(G/8)]}};
                    generated_mask[D+g] = |encode_mask[g*(G/8)+:(G/8)];
                end
            end
        end

        operand_isolation #(.WIDTH(D)) u_encode_isolation (
            .i_data(needs_commit ? merged_data : shifted_data),
            .i_isolate(!encode_enable),
            .o_data(encode_data)
        );

        if (PROTECTION_MODE == PROTECT_NONE) begin : g_none
            assign decoded_data = decode_code;
            assign repaired_code = decode_code;
            assign encoded_code = encode_data;
            assign parity_errors = '0;
            assign decode_good = 1'b1;
            assign decoded_corrected = 1'b0;
        end else if (PROTECTION_MODE == PROTECT_PARITY) begin : g_parity
            wire [PARITY_BITS-1:0] generated_parity;
            wire [PARITY_BITS-1:0] unused_valid;
            wire [D-1:0] unused_checked;
            wire unused_no_error;
            wire unused_any_error;
            logic good;

            parity #(.DATA_WIDTH(D), .PARITY_GRANULE_WIDTH(G)) u_parity (
                .i_generate_data(encode_data),
                .o_generated_parity(generated_parity),
                .i_check_data(decode_code[D-1:0]),
                .i_check_parity(decode_code[D+:PARITY_BITS]),
                .o_checked_data(unused_checked),
                .o_error_vector(parity_errors),
                .o_granule_valid(unused_valid),
                .o_no_error(unused_no_error),
                .o_any_error(unused_any_error)
            );

            // Reads check all intersecting granules. RMW checks only partially
            // overwritten groups; untouched and fully replaced groups need no trust.
            always_comb begin
                good = 1'b1;

                if (return_ok) begin
                    for (int g = 0; g < PARITY_BITS; g++) begin
                        if (returned_metadata.write ?
                            ((|saved_mask[g*(G/8)+:(G/8)]) &&
                                !(&saved_mask[g*(G/8)+:(G/8)])) :
                            (g * (G / 8) < 32'(returned_metadata.offset) +
                                (32'd1 << returned_metadata.size) &&
                                (g + 1) * (G / 8) > 32'(returned_metadata.offset))) begin

                            if (parity_errors[g] !== 1'b0) good = 1'b0;
                        end
                    end
                end
            end

            assign decode_good = good;
            assign decoded_corrected = 1'b0;
            assign decoded_data = decode_code[D-1:0];
            assign repaired_code = decode_code;
            assign encoded_code = {generated_parity, encode_data};
        end else begin : g_ecc
            wire no_error;
            wire corrected;
            wire uncorrectable;
            wire unused_scrub;
            wire unused_position_valid;
            wire [$clog2(ECC_WIDTH)-1:0] unused_position;
            wire [HAMMING_BITS-1:0] unused_syndrome;
            wire unused_overall;

            ecc #(.DATA_WIDTH(D)) u_ecc (
                .i_encode_data(encode_data),
                .o_encoded_codeword(encoded_code),
                .i_decode_codeword(decode_code),
                .o_decoded_data(decoded_data),
                .o_corrected_codeword(repaired_code),
                .o_no_error(no_error),
                .o_corrected(corrected),
                .o_uncorrectable(uncorrectable),
                .o_scrub_required(unused_scrub),
                .o_error_position_valid(unused_position_valid),
                .o_error_position(unused_position),
                .o_syndrome(unused_syndrome),
                .o_overall_parity_error(unused_overall)
            );

            assign parity_errors = '0;
            assign decode_good = {no_error, corrected, uncorrectable} === 3'b100 ||
                {no_error, corrected, uncorrectable} === 3'b010;
            assign decoded_corrected = decode_good && corrected === 1'b1;
        end

        logic [D-1:0] extracted_data;

        always_comb begin
            extracted_data = '0;

            if (decode_good && !returned_metadata.write) begin
                for (int b = 0; b < DATA_BYTES; b++) begin
                    if (b < (32'd1 << returned_metadata.size))
                        extracted_data[b*8+:8] =
                            8'(decoded_data >> (8 * (b + returned_metadata.offset)));
                end
            end

            decoded_result = {extracted_data, !decode_good,
                decode_good ? BANK_ERROR_WIDTH'(BANK_ERR_NONE) :
                PROTECTION_MODE == PROTECT_PARITY ? BANK_ERROR_WIDTH'(BANK_ERR_PARITY) :
                BANK_ERROR_WIDTH'(BANK_ERR_ECC_UNCORRECTABLE), decoded_corrected, !decode_good};
        end

        operand_isolation #(.WIDTH(1 + D + T + 1 + BANK_ERROR_WIDTH + 2)) u_response (
            .i_data({head_metadata.write, head_result.data, head_metadata.tag,
                head_result.error, head_result.code, head_result.corrected,
                head_result.uncorrectable}),
            .i_isolate(!o_rsp_valid),
            .o_data({o_rsp_write, o_rsp_rdata, o_rsp_tag, o_rsp_error, o_rsp_error_code,
                o_rsp_corrected, o_rsp_uncorrectable})
        );

        sram_wrapper #(
            .DATA_WIDTH(STORED_WIDTH),
            .DEPTH(WORDS),
            .MASK_GRANULARITY(GRANULE),
            .TAG_WIDTH(SLOT_WIDTH),
            .READ_LATENCY(LATENCY),
            .MAX_OUTSTANDING_READS(N),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_storage (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_flush(flushing),
            .i_req_valid(backend_req_valid),
            .o_req_ready(backend_req_ready),
            .i_req_write(backend_req_write),
            .i_req_addr(backend_address),
            .i_req_wdata(backend_write_data),
            .i_req_wmask(backend_write_mask),
            .i_req_tag(issue_pointer),
            .o_req_error(backend_req_error),
            .o_rsp_valid(backend_rsp_valid),
            .i_rsp_ready(backend_rsp_ready),
            .o_rsp_rdata(backend_rsp_data),
            .o_rsp_tag(backend_rsp_tag),
            .o_busy(backend_busy),
            .o_outstanding_reads(unused_backend_outstanding)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_flush_seen (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (i_flush === 1'b0 || i_flush === 1'b1)),
            .i_d(flushing),
            .o_q(flush_seen)
        );

        dff #(.WIDTH(8), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run),
            .i_d({request_accept, request_accept && legal && !write,
                request_accept && legal && write, response_accept, corrected_event,
                uncorrectable_event, scrub_event, flushing && !flush_seen}),
            .o_q(events)
        );

        logic [22:0] performance_events;
        always_comb begin
            performance_events = '0;
            performance_events[BANK_COUNT_READS] = request_accept && legal && !write;
            performance_events[BANK_COUNT_WRITES] = request_accept && legal && write;
            performance_events[BANK_COUNT_READ_BYTES] = request_accept && legal && !write;
            performance_events[BANK_COUNT_WRITE_BYTES] = request_accept && legal && write;
            performance_events[BANK_COUNT_READ_RESPONSES] = response_accept && !o_rsp_write;
            performance_events[BANK_COUNT_WRITE_RESPONSES] = response_accept && o_rsp_write;
            performance_events[BANK_COUNT_REQUEST_STALLS] = normal && offered && !o_req_ready;
            performance_events[BANK_COUNT_RESPONSE_STALLS] = o_rsp_valid && i_rsp_ready === 1'b0;
            performance_events[BANK_COUNT_FULL] = normal && !capacity;
            performance_events[BANK_COUNT_PARTIAL_WRITES] = request_accept && legal &&
                nonzero_write && shifted_mask != {DATA_BYTES{1'b1}};
            performance_events[BANK_COUNT_RMW] = request_accept && legal && rmw;
            performance_events[BANK_COUNT_WORK_STALLS] = normal && offered &&
                work_state !== BANK_WORK_IDLE;
            performance_events[BANK_COUNT_CORRECTED] = corrected_event;
            performance_events[BANK_COUNT_SCRUBS] = scrub_event;
            performance_events[BANK_COUNT_PARITY_ERRORS] = uncorrectable_event &&
                PROTECTION_MODE == PROTECT_PARITY;
            performance_events[BANK_COUNT_ECC_ERRORS] = uncorrectable_event &&
                PROTECTION_MODE == PROTECT_SECDED;
            performance_events[21:16] = illegal_events;
            performance_events[BANK_COUNT_FLUSHES] = flushing && !flush_seen;
            if (!run) performance_events = '0;
        end
`ifdef MOSAIC_SCRATCHPAD_BANK_INSTRUMENTATION
        scratchpad_bank_instrumentation #(.O(OCCUPANCY_WIDTH), .ASYNC_RESET(ASYNC_RESET))
        u_instrumentation (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_events(performance_events),
            .i_read_bytes(8'(read_bytes)),
            .i_write_bytes(8'(write_bytes)),
            .i_occupancy(o_outstanding)
        );
`endif
        for (genvar k = 0; k < 6; k++) begin : g_illegal_event
            assign illegal_events[k] = request_accept && request_error == BANK_ERROR_WIDTH'(k + 1);
        end
    end
endmodule
`default_nettype wire
