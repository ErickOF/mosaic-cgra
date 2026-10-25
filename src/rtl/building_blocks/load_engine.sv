`timescale 1ns / 1ps
`default_nettype none

// One descriptor owns an ordered circular table until every issued read retires.
// A response fills its tagged slot; only stream acceptance releases ownership.
module load_engine #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 128,
    parameter COUNT_WIDTH = 16,
    parameter MAX_ELEMENT_BYTES = 16,
    parameter MAX_OUTSTANDING = 8,
    parameter SPACE_ID_WIDTH = 2,
    parameter CHANNEL_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter ASYNC_RESET = 0,
    parameter MODE_WIDTH = 2,
    localparam bit PARAMETERS_VALID =
        ((ADDR_WIDTH >= 1) === 1'b1) && ( ^ ADDR_WIDTH !== 1'bx) &&
        ((DATA_WIDTH >= 8) === 1'b1) && ( ^ DATA_WIDTH !== 1'bx) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((COUNT_WIDTH >= 1) === 1'b1) && ( ^ COUNT_WIDTH !== 1'bx) &&
        ((MAX_ELEMENT_BYTES >= 1) === 1'b1) && ( ^ MAX_ELEMENT_BYTES !== 1'bx) &&
        (((MAX_ELEMENT_BYTES & (MAX_ELEMENT_BYTES - 1)) == 0) === 1'b1) &&
        ((MAX_ELEMENT_BYTES <= DATA_WIDTH / 8) === 1'b1) &&
        ((ADDR_WIDTH >= $clog2(MAX_ELEMENT_BYTES)) === 1'b1) &&
        ((MAX_OUTSTANDING >= 1) === 1'b1) && ( ^ MAX_OUTSTANDING !== 1'bx) &&
        ((SPACE_ID_WIDTH >= 1) === 1'b1) && ( ^ SPACE_ID_WIDTH !== 1'bx) &&
        ((CHANNEL_ID_WIDTH >= 1) === 1'b1) && ( ^ CHANNEL_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ^ CONTEXT_ID_WIDTH !== 1'bx) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) && (MODE_WIDTH === 2) &&
        ((64'(ADDR_WIDTH) + 64'(COUNT_WIDTH) + 3 < 64'd2147483647) === 1'b1) &&
        ((64'(MAX_OUTSTANDING) * (64'(DATA_WIDTH) + 64'(DATA_WIDTH) / 8 +
            64'(CHANNEL_ID_WIDTH) + 64'(CONTEXT_ID_WIDTH) + 8) < 64'd2147483647) === 1'b1),
    localparam int W = PARAMETERS_VALID ? ADDR_WIDTH : 1,
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 8,
    localparam int C = PARAMETERS_VALID ? COUNT_WIDTH : 1,
    localparam int N = PARAMETERS_VALID ? MAX_OUTSTANDING : 1,
    localparam int S = PARAMETERS_VALID ? SPACE_ID_WIDTH : 1,
    localparam int H = PARAMETERS_VALID ? CHANNEL_ID_WIDTH : 1,
    localparam int T = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int DATA_BYTES = D / 8,
    localparam int TAG_WIDTH = N > 1 ? $clog2(N) : 1,
    localparam int OCCUPANCY_WIDTH = $clog2(64'(N) + 1),
    localparam int MAX_ELEMENT_LOG2 = PARAMETERS_VALID ? $clog2(MAX_ELEMENT_BYTES) : 0,
    localparam int ELEMENT_SIZE_WIDTH = MAX_ELEMENT_LOG2 > 0 ? $clog2(MAX_ELEMENT_LOG2 + 1) : 1
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic [1:0] i_mode,
    input logic [W-1:0] i_base_address,
    input logic [C-1:0] i_inner_count,
    input logic [C-1:0] i_outer_count,
    input logic [W-1:0] i_inner_stride,
    input logic [W-1:0] i_outer_stride,
    input logic [ELEMENT_SIZE_WIDTH-1:0] i_element_size_log2,
    input logic [S-1:0] i_address_space,
    input logic [H-1:0] i_channel_id,
    input logic [T-1:0] i_context_id,
    input logic i_emit_end_of_stream,
    output logic o_mem_req_valid,
    input logic i_mem_req_ready,
    output logic [W-1:0] o_mem_req_address,
    output logic [ELEMENT_SIZE_WIDTH-1:0] o_mem_req_size_log2,
    output logic [TAG_WIDTH-1:0] o_mem_req_tag,
    output logic [S-1:0] o_mem_req_address_space,
    output logic [H-1:0] o_mem_req_channel_id,
    output logic [T-1:0] o_mem_req_context_id,
    input logic i_mem_rsp_valid,
    output logic o_mem_rsp_ready,
    input logic [TAG_WIDTH-1:0] i_mem_rsp_tag,
    input logic [D-1:0] i_mem_rsp_data,
    input logic i_mem_rsp_error,
    output logic o_stream_valid,
    input logic i_stream_ready,
    output logic [D-1:0] o_stream_data,
    output logic [DATA_BYTES-1:0] o_stream_keep,
    output logic o_stream_first,
    output logic o_stream_last,
    output logic o_stream_row_first,
    output logic o_stream_row_last,
    output logic o_stream_end_of_stream,
    output logic o_stream_error,
    output logic [H-1:0] o_stream_channel_id,
    output logic [T-1:0] o_stream_context_id,
    output logic o_idle,
    output logic o_busy,
    output logic o_command_started,
    output logic o_request_accepted,
    output logic o_response_accepted,
    output logic o_stream_accepted,
    output logic o_command_completed,
    output logic o_completed_with_error,
    output logic o_command_failed,
    output logic [OCCUPANCY_WIDTH-1:0] o_outstanding,
    output logic o_memory_error_seen,
    output logic o_error,
    output logic [load_engine_pkg::ERROR_CODE_WIDTH-1:0] o_error_code
);
    import agu_pkg::*;
    import load_engine_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        load_engine_parameters_must_be_valid invalid_parameters ();
    end else begin : g_engine
        // Struct dimensions depend on this instance and therefore remain local.
        typedef struct packed {
            logic [DATA_BYTES-1:0] keep;
            logic [H-1:0] channel_id;
            logic [T-1:0] context_id;
            logic first;
            logic last;
            logic row_first;
            logic row_last;
            logic end_of_stream;
        } metadata_t;
        localparam int M = $bits(metadata_t);
        localparam int REQUEST_BITS = W + ELEMENT_SIZE_WIDTH + TAG_WIDTH + S + H + T;
        localparam int STREAM_BITS = D + M + 1;

        wire run = i_rstb === 1'b1;
        // X/Z reset holds state; valid/ready outputs clamp until reset is known.
        wire reset_b = i_rstb !== 1'b0;
        logic active;
        logic [TAG_WIDTH-1:0] issue_pointer;
        logic [TAG_WIDTH-1:0] retire_pointer;
        wire [N-1:0] allocated;
        wire [N-1:0] present;
        wire [N-1:0] issue_select;
        wire [N-1:0] response_select;
        wire [N-1:0] response_write_enable;
        wire [N-1:0] unused_response_suppressed;
        wire [N-1:0] retire_select;
        wire unused_issue_valid;
        wire response_tag_valid;
        wire unused_retire_valid;
        wire [M-1:0] slot_metadata [N];
        wire [D:0] slot_response [N];
        metadata_t request_metadata;
        metadata_t head_metadata;
        wire [DATA_BYTES-1:0] head_keep = head_metadata.keep;
        wire [D:0] head_response = slot_response[retire_pointer];
        logic [D-1:0] byte_mask;
        logic [DATA_BYTES-1:0] request_keep;
        logic [W-1:0] alignment;
        load_error_t descriptor_error;
        load_error_t response_error;
        wire bounds_legal;
        wire [4:0] unused_bounds_error;
        wire [W:0] unused_lowest;
        wire [W:0] unused_limit;
        wire agu_config_ready;
        wire agu_valid;
        wire agu_error;
        wire [agu_pkg::ERROR_CODE_WIDTH-1:0] unused_agu_error_code;
        wire [W-1:0] agu_address;
        wire [ELEMENT_SIZE_WIDTH-1:0] agu_size;
        wire [S-1:0] agu_space;
        wire [H-1:0] agu_channel;
        wire [T-1:0] agu_context;
        wire agu_first;
        wire agu_last;
        wire agu_row_first;
        wire agu_row_last;
        wire agu_eos;
        wire [C-1:0] unused_inner;
        wire [C-1:0] unused_outer;
        wire unused_write;
        wire unused_agu_idle;
        wire unused_agu_active;
        wire unused_agu_started;
        wire unused_agu_accepted;
        wire unused_agu_completed;
        wire [2*C-1:0] unused_agu_count;
        wire [2:0] unused_occupancy_status;
        wire [6:0] events;

        wire config_accept = o_config_ready && (i_config_valid === 1'b1);
        wire start;
        wire reject;
        wire issue_enabled = run && active&&!o_error&&!agu_error &&
            (o_outstanding < OCCUPANCY_WIDTH'(N));
        wire agu_ready = issue_enabled && (i_mem_req_ready === 1'b1);
        wire request_accept = o_mem_req_valid && (i_mem_req_ready === 1'b1);
        wire response_accept = o_mem_rsp_ready && (i_mem_rsp_valid === 1'b1);
        wire response_store = response_accept && (response_error == LOAD_ERR_NONE);
        wire stream_accept = o_stream_valid && (i_stream_ready === 1'b1);
        wire runtime_error = active&&!o_error && agu_error;
        wire fatal_now = reject || runtime_error || (response_error != LOAD_ERR_NONE);
        // Malformed response has priority over simultaneous descriptor/AGU faults.
        wire [load_engine_pkg::ERROR_CODE_WIDTH-1:0] fatal_code =
            response_error != LOAD_ERR_NONE ? response_error :
            reject ? descriptor_error : LOAD_ERR_AGU;
        wire clear_error = run&&!active && (o_outstanding == '0) &&
            (i_error_clear === 1'b1)&&!fatal_now;
        wire [load_engine_pkg::ERROR_CODE_WIDTH-1:0] next_error_code =
            clear_error ? LOAD_ERR_NONE : fatal_code;
        wire [OCCUPANCY_WIDTH-1:0] remaining = o_outstanding +
            OCCUPANCY_WIDTH'(request_accept) - OCCUPANCY_WIDTH'(stream_accept);
        wire finish = stream_accept && head_metadata.last&&!o_error&&!fatal_now;
        wire fail = reject || ((o_error || fatal_now) && (active || start) &&
            (remaining == '0));
        wire [TAG_WIDTH-1:0] next_issue = issue_pointer == TAG_WIDTH'(N - 1)
            ? '0 : issue_pointer + 1'b1;
        wire [TAG_WIDTH-1:0] next_retire = retire_pointer == TAG_WIDTH'(N - 1)
            ? '0 : retire_pointer + 1'b1;

        // A consumed illegal descriptor reports rejection without clocking the
        // AGU or starting a command. Both events share the common write policy.
        write_gate u_descriptor_write (
            .i_write_enable(config_accept),
            .i_suppress(descriptor_error != load_engine_pkg::LOAD_ERR_NONE),
            .o_write_enable(start),
            .o_write_suppressed(reject)
        );

        assign o_config_ready = run&&!active && (o_outstanding == '0)&&!o_error &&
            agu_config_ready && (i_error_clear === 1'b0);
        assign o_mem_req_valid = issue_enabled && agu_valid;
        assign o_mem_rsp_ready = run;
        assign o_stream_valid = run && allocated[retire_pointer] && present[retire_pointer];
        assign o_error = o_error_code != LOAD_ERR_NONE;
        assign o_busy = active || (o_outstanding != '0);
        assign o_idle = !o_busy&&!o_error;
        assign {o_command_started, o_request_accepted, o_response_accepted,
            o_stream_accepted, o_command_completed, o_completed_with_error,
            o_command_failed} = run ? events : '0;

        // Reuse the DMA affine checker to reject the entire address rectangle
        // before configuring the AGU. It also checks the final element's bytes.
        dma_engine_bounds #(
            .W(W),
            .C(C),
            .SIZE_WIDTH(ELEMENT_SIZE_WIDTH),
            .MAX_ELEMENT_LOG2(MAX_ELEMENT_LOG2)
        ) u_bounds (
            .i_enable(config_accept),
            .i_mode(i_mode),
            .i_base(i_base_address),
            .i_inner_stride(i_inner_stride),
            .i_outer_stride(i_outer_stride),
            .i_inner_count(i_inner_count),
            .i_outer_count(i_outer_count),
            .i_size(i_element_size_log2),
            .o_legal(bounds_legal),
            .o_error(unused_bounds_error),
            .o_lowest(unused_lowest),
            .o_limit(unused_limit)
        );

        // Check all descriptor fields, including ignored strides, for knownness.
        // The AGU still performs its own validation through its public interface.
        always_comb begin
            descriptor_error = LOAD_ERR_NONE;
            alignment = '0;

            if (config_accept) begin
                alignment = W'(({{W{1'b0}}, 1'b1} << i_element_size_log2) - 1'b1);
                if ( ^ {i_mode, i_base_address, i_inner_count, i_outer_count,
                    i_inner_stride, i_outer_stride, i_element_size_log2, i_address_space,
                    i_channel_id, i_context_id, i_emit_end_of_stream} === 1'bx)
                    descriptor_error = LOAD_ERR_DESCRIPTOR_UNKNOWN;
                else if (i_mode == 2'b11) descriptor_error = LOAD_ERR_MODE;
                else if (i_inner_count == '0) descriptor_error = LOAD_ERR_INNER_COUNT;
                else if (i_outer_count == '0) descriptor_error = LOAD_ERR_OUTER_COUNT;
                else if ((i_mode != AGU_STRIDED_2D) && (i_outer_count != C'(1)))
                    descriptor_error = LOAD_ERR_1D_OUTER_COUNT;
                else if (32'(i_element_size_log2) > MAX_ELEMENT_LOG2)
                    descriptor_error = LOAD_ERR_ELEMENT_SIZE;
                else if ( | (i_base_address & alignment))
                    descriptor_error = LOAD_ERR_BASE_ALIGNMENT;
                else if ((i_mode != AGU_LINEAR_1D) && ( | (i_inner_stride & alignment)))
                    descriptor_error = LOAD_ERR_INNER_ALIGNMENT;
                else if ((i_mode == AGU_STRIDED_2D) && ( | (i_outer_stride & alignment)))
                    descriptor_error = LOAD_ERR_OUTER_ALIGNMENT;
                else if (!bounds_legal) descriptor_error = LOAD_ERR_ADDRESS_RANGE;
            end
        end

        // Sticky fatal state resets only the address generator. This aborts its
        // unissued tail without advancing it or resetting any owned reorder slot.
        // The reset source is registered, never a combinational protocol fault.
        agu #(
            .ADDR_WIDTH(W),
            .COUNT_WIDTH(C),
            .MAX_ELEMENT_BYTES(MAX_ELEMENT_BYTES),
            .SPACE_ID_WIDTH(S),
            .CHANNEL_ID_WIDTH(H),
            .CONTEXT_ID_WIDTH(T),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_agu (
            .i_clk(i_clk),
            .i_rstb(reset_b&&!o_error),
            .i_error_clear(1'b0),
            .i_config_valid(start),
            .o_config_ready(agu_config_ready),
            .i_mode(i_mode),
            .i_base_address(i_base_address),
            .i_inner_count(i_inner_count),
            .i_outer_count(i_outer_count),
            .i_inner_stride(i_inner_stride),
            .i_outer_stride(i_outer_stride),
            .i_element_size_log2(i_element_size_log2),
            .i_is_write(1'b0),
            .i_address_space(i_address_space),
            .i_channel_id(i_channel_id),
            .i_context_id(i_context_id),
            .i_emit_end_of_stream(i_emit_end_of_stream),
            .o_valid(agu_valid),
            .i_ready(agu_ready),
            .o_address(agu_address),
            .o_inner_index(unused_inner),
            .o_outer_index(unused_outer),
            .o_first(agu_first),
            .o_last(agu_last),
            .o_row_first(agu_row_first),
            .o_row_last(agu_row_last),
            .o_end_of_stream(agu_eos),
            .o_element_size_log2(agu_size),
            .o_is_write(unused_write),
            .o_address_space(agu_space),
            .o_channel_id(agu_channel),
            .o_context_id(agu_context),
            .o_idle(unused_agu_idle),
            .o_active(unused_agu_active),
            .o_descriptor_started(unused_agu_started),
            .o_address_accepted(unused_agu_accepted),
            .o_completed(unused_agu_completed),
            .o_addresses_accepted(unused_agu_count),
            .o_error(agu_error),
            .o_error_code(unused_agu_error_code)
        );

        decoder #(.NUM_OUTPUTS(N)) u_issue_decode (
            .i_enable(request_accept),
            .i_select(issue_pointer),
            .o_decoded(issue_select),
            .o_select_valid(unused_issue_valid)
        );

        decoder #(.NUM_OUTPUTS(N)) u_response_decode (
            .i_enable(response_accept),
            .i_select(i_mem_rsp_tag),
            .o_decoded(response_select),
            .o_select_valid(response_tag_valid)
        );

        decoder #(.NUM_OUTPUTS(N)) u_retire_decode (
            .i_enable(stream_accept),
            .i_select(retire_pointer),
            .o_decoded(retire_select),
            .o_select_valid(unused_retire_valid)
        );

        // Decode the consumed tag first, then suppress every entry update for
        // malformed responses. Legal reads that report a memory error still
        // write their ordered zero-data/error response into the selected slot.
        write_gate #(.WIDTH(N)) u_response_write (
            .i_write_enable(response_select),
            .i_suppress({N{response_error != load_engine_pkg::LOAD_ERR_NONE}}),
            .o_write_enable(response_write_enable),
            .o_write_suppressed(unused_response_suppressed)
        );

        always_comb begin
            response_error = LOAD_ERR_NONE;

            if (response_accept) begin
                if ( ^ {i_mem_rsp_tag, i_mem_rsp_error} === 1'bx)
                    response_error = LOAD_ERR_RESPONSE_UNKNOWN;
                else if (!response_tag_valid) response_error = LOAD_ERR_TAG_RANGE;
                else if (!allocated[i_mem_rsp_tag]) response_error = LOAD_ERR_TAG_UNALLOCATED;
                else if (present[i_mem_rsp_tag]) response_error = LOAD_ERR_TAG_DUPLICATE;
            end
        end

        always_comb begin
            request_keep = '0;

            for (int b = 0; b < DATA_BYTES; b++)
                request_keep[b] = o_mem_req_valid && (b < (32'(1) << agu_size));

            request_metadata = {request_keep, agu_channel, agu_context, agu_first, agu_last,
                agu_row_first, agu_row_last, agu_eos};
            head_metadata = slot_metadata[retire_pointer];
            byte_mask = '0;

            for (int b = 0; b < DATA_BYTES; b++)
                byte_mask[b*8+:8] = {8{o_stream_valid && head_keep[b]}};
        end

        for (genvar n = 0; n < N; n++) begin : g_slot
            wire fill = response_write_enable[n];

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_allocated (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(issue_select[n] || retire_select[n]),
                .i_d(issue_select[n]),
                .o_q(allocated[n])
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_present (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(issue_select[n] || retire_select[n] || fill),
                .i_d(fill),
                .o_q(present[n])
            );

            // Payload banks are unreset and write only their qualified event.
            dff #(.WIDTH(M)) u_metadata (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(issue_select[n]),
                .i_d(request_metadata),
                .o_q(slot_metadata[n])
            );

            dff #(.WIDTH(D + 1)) u_response (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(fill),
                .i_d({i_mem_rsp_error, i_mem_rsp_error ? {D{1'b0}} : i_mem_rsp_data}),
                .o_q(slot_response[n])
            );
        end

        dff #(.WIDTH(TAG_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_issue_pointer (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(request_accept),
            .i_d(next_issue),
            .o_q(issue_pointer)
        );

        dff #(.WIDTH(TAG_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_retire_pointer (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(stream_accept),
            .i_d(next_retire),
            .o_q(retire_pointer)
        );

        counter #(
            .WIDTH(OCCUPANCY_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(0)
        ) u_occupancy (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(request_accept ^ stream_accept),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(stream_accept),
            .i_load_value({OCCUPANCY_WIDTH{1'b0}}),
            .o_count(o_outstanding),
            .o_overflow(unused_occupancy_status[0]),
            .o_underflow(unused_occupancy_status[1]),
            .o_terminal(unused_occupancy_status[2])
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_active (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (start || finish || fail)),
            .i_d(start&&!fail),
            .o_q(active)
        );

        dff #(
            .WIDTH(load_engine_pkg::ERROR_CODE_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (clear_error || (fatal_now&&!o_error))),
            .i_d(next_error_code),
            .o_q(o_error_code)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_memory_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(config_accept || (response_store && (i_mem_rsp_error === 1'b1))),
            .i_d(!config_accept),
            .o_q(o_memory_error_seen)
        );

        dff #(.WIDTH(7), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run),
            .i_d({start, request_accept, response_accept, stream_accept, finish,
                finish && o_memory_error_seen, fail}),
                .o_q(events)
        );

        operand_isolation #(.WIDTH(REQUEST_BITS)) u_request_output (
            .i_data({agu_address, agu_size, issue_pointer, agu_space, agu_channel, agu_context}),
            .i_isolate(!o_mem_req_valid),
            .o_data({o_mem_req_address, o_mem_req_size_log2,
                o_mem_req_tag, o_mem_req_address_space, o_mem_req_channel_id, o_mem_req_context_id})
        );

        operand_isolation #(.WIDTH(STREAM_BITS)) u_stream_output (
            .i_data({head_response[D] ? {D{1'b0}} : head_response[D-1:0] & byte_mask,
                head_metadata, head_response[D]}),
            .i_isolate(!o_stream_valid),
            .o_data({o_stream_data, o_stream_keep, o_stream_channel_id, o_stream_context_id,
                o_stream_first, o_stream_last, o_stream_row_first, o_stream_row_last,
                o_stream_end_of_stream, o_stream_error})
        );

`ifdef MOSAIC_LOAD_ENGINE_ASSERTIONS
        load_engine_assertions #(
            .N(N),
            .D(D),
            .M(M),
            .TAG_WIDTH(TAG_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_assertions (.*);
`endif
    end
endmodule
`default_nettype wire
