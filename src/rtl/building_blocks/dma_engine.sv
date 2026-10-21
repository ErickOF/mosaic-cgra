`timescale 1ns / 1ps

// Descriptor scheduler over external load/store backend interfaces.
// Parameters deliberately remain untyped until PARAMETERS_VALID checks them:
// a bit parameter would silently coerce an illegal X/Z or nonbinary flag.
module dma_engine #(
    parameter NUM_CHANNELS = 2,
    parameter COMMAND_QUEUE_DEPTH = 4,
    parameter DATA_FIFO_DEPTH = 8,
    parameter COMPLETION_QUEUE_DEPTH = 4,
    parameter EVENT_QUEUE_DEPTH = 4,
    parameter DATA_WIDTH = 128,
    parameter ADDR_WIDTH = 40,
    parameter COUNT_WIDTH = 16,
    parameter MODE_WIDTH = 2,
    parameter SPACE_ID_WIDTH = 4,
    parameter STREAM_ID_WIDTH = 8,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter COMMAND_ID_WIDTH = 12,
    parameter PRIORITY_WIDTH = 3,
    parameter NUM_EVENTS = 16,
    parameter NUM_PROTECTION_REGIONS = 8,
    parameter MAX_BURST_BEATS = 16,
    parameter TRANSFER_TIMEOUT_CYCLES = 65535,
    parameter CANCEL_TIMEOUT_CYCLES = 1024,
    parameter DESCRIPTOR_EPOCH_WIDTH = 2,
    parameter SUPPORT_EVENT_START = 1,
    parameter SUPPORT_CANCELLATION = 1,
    parameter PROTECT_COMMAND_FIFO = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_CHANNELS >= 1) === 1'b1) && ( ^ NUM_CHANNELS !== 1'bx) &&
        ((COMMAND_QUEUE_DEPTH >= 1) === 1'b1) && ( ^ COMMAND_QUEUE_DEPTH !== 1'bx) &&
        ((DATA_FIFO_DEPTH >= 1) === 1'b1) && ( ^ DATA_FIFO_DEPTH !== 1'bx) &&
        ((COMPLETION_QUEUE_DEPTH >= 1) === 1'b1) && ( ^ COMPLETION_QUEUE_DEPTH !== 1'bx) &&
        ((EVENT_QUEUE_DEPTH >= 1) === 1'b1) && ( ^ EVENT_QUEUE_DEPTH !== 1'bx) &&
        ((DATA_WIDTH >= 1) === 1'b1) && ( ^ DATA_WIDTH !== 1'bx) &&
        ((ADDR_WIDTH >= 1) === 1'b1) && ( ^ ADDR_WIDTH !== 1'bx) &&
        ((COUNT_WIDTH >= 1) === 1'b1) && ( ^ COUNT_WIDTH !== 1'bx) &&
        ((SPACE_ID_WIDTH >= 1) === 1'b1) && ( ^ SPACE_ID_WIDTH !== 1'bx) &&
        ((STREAM_ID_WIDTH >= 1) === 1'b1) && ( ^ STREAM_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ^ CONTEXT_ID_WIDTH !== 1'bx) &&
        ((COMMAND_ID_WIDTH >= 1) === 1'b1) && ( ^ COMMAND_ID_WIDTH !== 1'bx) &&
        ((PRIORITY_WIDTH >= 1) === 1'b1) && ( ^ PRIORITY_WIDTH !== 1'bx) &&
        ((NUM_EVENTS >= 1) === 1'b1) && ( ^ NUM_EVENTS !== 1'bx) &&
        ((NUM_PROTECTION_REGIONS >= 1) === 1'b1) && ( ^ NUM_PROTECTION_REGIONS !== 1'bx) &&
        ((MAX_BURST_BEATS >= 1) === 1'b1) && ( ^ MAX_BURST_BEATS !== 1'bx) &&
        ((TRANSFER_TIMEOUT_CYCLES >= 1) === 1'b1) && ( ^ TRANSFER_TIMEOUT_CYCLES !== 1'bx) &&
        ((CANCEL_TIMEOUT_CYCLES >= 1) === 1'b1) && ( ^ CANCEL_TIMEOUT_CYCLES !== 1'bx) &&
        ((SUPPORT_EVENT_START === 0) || (SUPPORT_EVENT_START === 1)) &&
        ((SUPPORT_CANCELLATION === 0) || (SUPPORT_CANCELLATION === 1)) &&
        ((PROTECT_COMMAND_FIFO === 0) || (PROTECT_COMMAND_FIFO === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((64'(MAX_BURST_BEATS) <= 64'h7fffffffffffffff) === 1'b1) &&
        ((64'(TRANSFER_TIMEOUT_CYCLES) <= 64'h7fffffffffffffff) === 1'b1) &&
        ((64'(CANCEL_TIMEOUT_CYCLES) <= 64'h7fffffffffffffff) === 1'b1) &&
        ((64'(DATA_FIFO_DEPTH) * (64'(DATA_WIDTH) + 64'(DATA_WIDTH) / 8 + 64'(CONTEXT_ID_WIDTH) +
            64'(STREAM_ID_WIDTH) + 64'(COMMAND_ID_WIDTH) + 64'(DESCRIPTOR_EPOCH_WIDTH) + 3) <
            64'd2147483647) === 1'b1) &&
        ((64'(COMPLETION_QUEUE_DEPTH) * (64'(NUM_CHANNELS) + 64'(CONTEXT_ID_WIDTH) +
            64'(COMMAND_ID_WIDTH) + 4 * 64'(COUNT_WIDTH) + 128) < 64'd2147483647) === 1'b1) &&
        ((64'(EVENT_QUEUE_DEPTH) * (64'(NUM_EVENTS) + 64'(CONTEXT_ID_WIDTH) + 64'(COMMAND_ID_WIDTH)
            + 1) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_PROTECTION_REGIONS) * (2 * 64'(ADDR_WIDTH) + 64'(CONTEXT_ID_WIDTH) +
            64'(SPACE_ID_WIDTH) + 4) < 64'd2147483647) === 1'b1) &&
        (MODE_WIDTH === 2) &&
        ((DESCRIPTOR_EPOCH_WIDTH >= 2) === 1'b1) && ( ^ DESCRIPTOR_EPOCH_WIDTH !== 1'bx) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        (((DATA_WIDTH / 8 & ((DATA_WIDTH / 8) - 1)) == 0) === 1'b1) &&
        ((64'(NUM_CHANNELS) * (64'(DATA_WIDTH) + 64'(ADDR_WIDTH) * 6 + 64'(COUNT_WIDTH) * 4 +
            64'(NUM_EVENTS) + 64'(NUM_PROTECTION_REGIONS) + 64'(SPACE_ID_WIDTH) * 2 +
            64'(CONTEXT_ID_WIDTH) * 2 + 64'(STREAM_ID_WIDTH) + 64'(COMMAND_ID_WIDTH) +
            64'(PRIORITY_WIDTH) + 64'(DESCRIPTOR_EPOCH_WIDTH) + 256) < 64'd2147483647) === 1'b1) &&
        ((64'(COMMAND_QUEUE_DEPTH) * (64'(DATA_WIDTH) + 64'(ADDR_WIDTH) * 6 + 64'(COUNT_WIDTH) * 4 +
            64'(NUM_EVENTS) + 64'(SPACE_ID_WIDTH) * 2 + 64'(CONTEXT_ID_WIDTH) * 2 +
            64'(STREAM_ID_WIDTH) + 64'(COMMAND_ID_WIDTH) + 64'(PRIORITY_WIDTH) + 256) <
            64'd2147483647) === 1'b1),
    localparam int N = PARAMETERS_VALID ? NUM_CHANNELS : 1,
    localparam int Q = PARAMETERS_VALID ? COMMAND_QUEUE_DEPTH : 1,
    localparam int DQ = PARAMETERS_VALID ? DATA_FIFO_DEPTH : 1,
    localparam int CQ = PARAMETERS_VALID ? COMPLETION_QUEUE_DEPTH : 1,
    localparam int EQ = PARAMETERS_VALID ? EVENT_QUEUE_DEPTH : 1,
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int W = PARAMETERS_VALID ? ADDR_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? COUNT_WIDTH : 1,
    localparam int S = PARAMETERS_VALID ? SPACE_ID_WIDTH : 1,
    localparam int I = PARAMETERS_VALID ? STREAM_ID_WIDTH : 1,
    localparam int X = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int J = PARAMETERS_VALID ? COMMAND_ID_WIDTH : 1,
    localparam int P = PARAMETERS_VALID ? PRIORITY_WIDTH : 1,
    localparam int V = PARAMETERS_VALID ? NUM_EVENTS : 1,
    localparam int R = PARAMETERS_VALID ? NUM_PROTECTION_REGIONS : 1,
    localparam int EP = PARAMETERS_VALID ? DESCRIPTOR_EPOCH_WIDTH : 1,
    localparam int DATA_BYTES = D / 8 > 0 ? D / 8 : 1,
    localparam int MAX_ELEMENT_BYTES_LOG2 = $clog2(DATA_BYTES),
    localparam int SIZE_WIDTH = MAX_ELEMENT_BYTES_LOG2 > 0 ? $clog2(MAX_ELEMENT_BYTES_LOG2 + 1) : 1,
    localparam int CHANNEL_WIDTH = N > 1 ? $clog2(N) : 1,
    localparam int EVENT_ID_WIDTH = V > 1 ? $clog2(V) : 1,
    localparam int REGION_ID_WIDTH = R > 1 ? $clog2(R) : 1,
    localparam int BURST_WIDTH = PARAMETERS_VALID ? $clog2(64'(MAX_BURST_BEATS) + 1) : 1,
    localparam int COMMAND_OCCUPANCY_WIDTH = $clog2(Q + 1),
    localparam int DATA_OCCUPANCY_WIDTH = $clog2(DQ + 1),
    localparam int BYTE_COUNT_WIDTH = 2 * C + MAX_ELEMENT_BYTES_LOG2 + 1,
    localparam int TIMEOUT_WIDTH = PARAMETERS_VALID ? $clog2(64'(TRANSFER_TIMEOUT_CYCLES) + 1) : 1,
    localparam int CANCEL_TIMEOUT_WIDTH = PARAMETERS_VALID ? $clog2(
        64'(CANCEL_TIMEOUT_CYCLES) + 1
    ) : 1
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_region_valid,
    output logic o_region_ready,
    input logic [REGION_ID_WIDTH-1:0] i_region_index,
    input logic i_region_enable,
    input logic [S-1:0] i_region_space_id,
    input logic [W-1:0] i_region_base,
    input logic [W:0] i_region_limit,
    input logic [X-1:0] i_region_context_id,
    input logic i_region_read_enable,
    input logic i_region_write_enable,
    output logic o_region_updated,
    output logic o_region_rejected,
    input logic [V-1:0] i_event_pending,
    input logic i_command_valid,
    output logic o_command_ready,
    input logic [CHANNEL_WIDTH-1:0] i_command_channel,
    input logic [1:0] i_command_mode,
    input logic [1:0] i_command_address_mode,
    input logic [SIZE_WIDTH-1:0] i_command_element_size_log2,
    input logic [S-1:0] i_command_source_space,
    input logic [S-1:0] i_command_destination_space,
    input logic [W-1:0] i_command_source_base,
    input logic [W-1:0] i_command_destination_base,
    input logic [C-1:0] i_command_inner_count,
    input logic [C-1:0] i_command_outer_count,
    input logic [W-1:0] i_command_source_inner_stride,
    input logic [W-1:0] i_command_destination_inner_stride,
    input logic [W-1:0] i_command_source_outer_stride,
    input logic [W-1:0] i_command_destination_outer_stride,
    input logic [REGION_ID_WIDTH-1:0] i_command_source_region,
    input logic [REGION_ID_WIDTH-1:0] i_command_destination_region,
    input logic [I-1:0] i_command_stream_id,
    input logic [X-1:0] i_command_context_id,
    input logic [J-1:0] i_command_id,
    input logic [1:0] i_command_start_mode,
    input logic [V-1:0] i_command_start_event_mask,
    input logic i_command_completion_event_enable,
    input logic [EVENT_ID_WIDTH-1:0] i_command_completion_event_id,
    input logic i_command_stream_last,
    input logic [P-1:0] i_command_priority,
    input logic [BURST_WIDTH-1:0] i_command_max_burst_beats,
    output logic o_command_accepted,
    output logic o_command_rejected,
    input logic i_cancel_valid,
    output logic o_cancel_ready,
    input logic [CHANNEL_WIDTH-1:0] i_cancel_channel,
    input logic [X-1:0] i_cancel_context_id,
    input logic [J-1:0] i_cancel_command_id,
    output logic o_cancel_accepted,
    output logic o_cancel_not_found,
    input logic [N-1:0] i_stream_valid,
    output logic [N-1:0] o_stream_ready,
    input logic [N*D-1:0] i_stream_data,
    input logic [N*DATA_BYTES-1:0] i_stream_keep,
    input logic [N-1:0] i_stream_first,
    input logic [N-1:0] i_stream_descriptor_last,
    input logic [N-1:0] i_stream_last,
    input logic [N*I-1:0] i_stream_id,
    input logic [N*X-1:0] i_stream_context_id,
    input logic [N-1:0] i_stream_error,
    output logic [N-1:0] o_stream_valid,
    input logic [N-1:0] i_stream_ready,
    output logic [N*D-1:0] o_stream_data,
    output logic [N*DATA_BYTES-1:0] o_stream_keep,
    output logic [N-1:0] o_stream_first,
    output logic [N-1:0] o_stream_descriptor_last,
    output logic [N-1:0] o_stream_last,
    output logic [N*I-1:0] o_stream_id,
    output logic [N*X-1:0] o_stream_context_id,
    output logic [N-1:0] o_stream_error,
    output logic [N-1:0] o_load_config_valid,
    input logic [N-1:0] i_load_config_ready,
    input logic [N-1:0] i_load_config_rejected,
    output logic [N*2-1:0] o_load_mode,
    output logic [N*SIZE_WIDTH-1:0] o_load_element_size_log2,
    output logic [N*W-1:0] o_load_base_address,
    output logic [N*C-1:0] o_load_inner_count,
    output logic [N*C-1:0] o_load_outer_count,
    output logic [N*W-1:0] o_load_inner_stride,
    output logic [N*W-1:0] o_load_outer_stride,
    output logic [N*S-1:0] o_load_space_id,
    output logic [N*X-1:0] o_load_context_id,
    output logic [N*I-1:0] o_load_channel_id,
    output logic [N*BURST_WIDTH-1:0] o_load_max_burst_beats,
    output logic [N*P-1:0] o_load_priority,
    output logic [N*EP-1:0] o_load_descriptor_epoch,
    input logic [N-1:0] i_load_stream_valid,
    output logic [N-1:0] o_load_stream_ready,
    input logic [N*D-1:0] i_load_stream_data,
    input logic [N*DATA_BYTES-1:0] i_load_stream_keep,
    input logic [N-1:0] i_load_stream_first,
    input logic [N-1:0] i_load_stream_last,
    input logic [N-1:0] i_load_stream_error,
    input logic [N-1:0] i_load_done,
    input logic [N-1:0] i_load_done_error,
    input logic [N*EP-1:0] i_load_done_epoch,
    // The epoch travels with each load beat and must hold during backpressure.
    input logic [N*EP-1:0] i_load_stream_epoch,
    output logic [N-1:0] o_load_cancel,
    input logic [N-1:0] i_load_cancel_done,
    output logic [N-1:0] o_store_config_valid,
    input logic [N-1:0] i_store_config_ready,
    input logic [N-1:0] i_store_config_rejected,
    output logic [N*2-1:0] o_store_mode,
    output logic [N*SIZE_WIDTH-1:0] o_store_element_size_log2,
    output logic [N*W-1:0] o_store_base_address,
    output logic [N*C-1:0] o_store_inner_count,
    output logic [N*C-1:0] o_store_outer_count,
    output logic [N*W-1:0] o_store_inner_stride,
    output logic [N*W-1:0] o_store_outer_stride,
    output logic [N*S-1:0] o_store_space_id,
    output logic [N*X-1:0] o_store_context_id,
    output logic [N*I-1:0] o_store_channel_id,
    output logic [N*BURST_WIDTH-1:0] o_store_max_burst_beats,
    output logic [N*P-1:0] o_store_priority,
    output logic [N*EP-1:0] o_store_descriptor_epoch,
    output logic [N-1:0] o_store_stream_valid,
    input logic [N-1:0] i_store_stream_ready,
    output logic [N*D-1:0] o_store_stream_data,
    output logic [N*DATA_BYTES-1:0] o_store_stream_keep,
    output logic [N-1:0] o_store_stream_first,
    output logic [N-1:0] o_store_stream_last,
    output logic [N-1:0] o_store_stream_error,
    input logic [N-1:0] i_store_done,
    input logic [N-1:0] i_store_done_error,
    input logic [N*EP-1:0] i_store_done_epoch,
    // Per-descriptor cumulative committed bytes, held through done/cancel done.
    // Stream acceptance alone is not evidence that a memory write committed.
    input logic [N*BYTE_COUNT_WIDTH-1:0] i_store_bytes_committed,
    output logic [N-1:0] o_store_cancel,
    input logic [N-1:0] i_store_cancel_done,
    output logic o_completion_valid,
    input logic i_completion_ready,
    output logic [CHANNEL_WIDTH-1:0] o_completion_channel,
    output logic [X-1:0] o_completion_context_id,
    output logic [J-1:0] o_completion_command_id,
    output logic [1:0] o_completion_status,
    output logic [BYTE_COUNT_WIDTH-1:0] o_completion_bytes_read,
    output logic [BYTE_COUNT_WIDTH-1:0] o_completion_bytes_written,
    output logic [4:0] o_completion_error_code,
    output logic o_event_valid,
    input logic i_event_ready,
    output logic [EVENT_ID_WIDTH-1:0] o_event_id,
    output logic [X-1:0] o_event_context_id,
    output logic [J-1:0] o_event_command_id,
    output logic o_event_error,
    output logic [N-1:0] o_channel_busy,
    output logic [N-1:0] o_channel_canceling,
    output logic [N*COMMAND_OCCUPANCY_WIDTH-1:0] o_command_occupancy,
    output logic [N*DATA_OCCUPANCY_WIDTH-1:0] o_data_fifo_occupancy,
    output logic [EP-1:0] o_descriptor_epoch,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic o_fatal_error,
    output logic [4:0] o_error_code,
    output logic [N-1:0] o_event_command_start,
    output logic [N-1:0] o_event_command_complete,
    output logic [N-1:0] o_event_command_stall,
    output logic [N-1:0] o_event_data_stall,
    output logic [N-1:0] o_event_timeout
);
    import dma_engine_pkg::*;

    // Combinational logic assigns defaults before every conditional path.
    // Sequential state has a single always_ff writer for each reset variant.

    // Payload widths depend on this module's parameters, so their packed
    // structs stay local. Shared enum encodings live in dma_engine_pkg.
    typedef struct packed {
        logic [1:0] mode;
        logic [1:0] address_mode;
        logic [1:0] start_mode;
        logic [W-1:0] source_base;
        logic [W-1:0] destination_base;
        logic [W-1:0] source_inner;
        logic [W-1:0] destination_inner;
        logic [W-1:0] source_outer;
        logic [W-1:0] destination_outer;
        logic [C-1:0] inner_count;
        logic [C-1:0] outer_count;
        logic [SIZE_WIDTH-1:0] size;
        logic [S-1:0] source_space;
        logic [S-1:0] destination_space;
        logic [REGION_ID_WIDTH-1:0] source_region;
        logic [REGION_ID_WIDTH-1:0] destination_region;
        logic [I-1:0] stream_id;
        logic [X-1:0] context_id;
        logic [J-1:0] command_id;
        logic [V-1:0] event_mask;
        logic event_enable;
        logic stream_last;
        logic [EVENT_ID_WIDTH-1:0] event_id;
        logic [P-1:0] priority_hint;
        logic [BURST_WIDTH-1:0] burst;
        logic [2*C-1:0] elements;
        logic [BYTE_COUNT_WIDTH-1:0] bytes;
    } command_t;

    typedef struct packed {
        logic [CHANNEL_WIDTH-1:0] channel;
        logic [X-1:0] context_id;
        logic [J-1:0] command_id;
        logic [1:0] status;
        logic [BYTE_COUNT_WIDTH-1:0] bytes_read;
        logic [BYTE_COUNT_WIDTH-1:0] bytes_written;
        logic [4:0] error_code;
    } completion_t;

    typedef struct packed {
        logic [EVENT_ID_WIDTH-1:0] id;
        logic [X-1:0] context_id;
        logic [J-1:0] command_id;
        logic error;
    } event_t;

    localparam int COMMAND_BITS = $bits(command_t);
    localparam int COMPLETION_BITS = $bits(completion_t);
    localparam int EVENT_BITS = $bits(event_t);
    command_t command;
    completion_t completion_record;
    event_t event_record;
    localparam int BEAT_BITS = D + DATA_BYTES + 3 + X + I + J + EP;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        dma_engine_parameters_must_be_valid invalid_parameters ();
    end else begin : g_dma
        logic [R-1:0] region_enabled;
        logic [R-1:0] region_read;
        logic [R-1:0] region_write;
        logic [W-1:0] region_base[R];
        logic [W:0] region_limit[R];
        logic [S-1:0] region_space[R];
        logic [X-1:0] region_context[R];
        logic flushing;
        logic flush_seen;
        logic [EP-1:0] epoch;
        logic [4:0] engine_error;
        logic fatal_error;
        logic [COMMAND_BITS-1:0] active_packet[N];
        // Extract shared metadata through the packed type once per channel.
        // Consumers must not depend on manually maintained descriptor offsets.
        wire [X-1:0] active_context[N];
        wire [J-1:0] active_id[N];
        wire [EVENT_ID_WIDTH-1:0] active_event_id[N];
        dma_phase_t phase[N];
        logic [N-1:0] queue_ready;
        logic [N-1:0] queue_valid;
        logic [N-1:0] queue_pop;
        logic [N-1:0] queue_canceled;
        logic [N-1:0] queue_corrupt;
        logic [N-1:0] queue_duplicate;
        logic [N-1:0] queue_cancel_match;
        logic [N-1:0] queue_cancel;
        logic [N-1:0] active_cancel;
        logic [N-1:0] completion_pending;
        logic [N-1:0] retire;
        logic [N-1:0] local_fatal;
        logic [4:0] local_error[N];
        logic [1:0] result_status[N];
        logic [4:0] command_error[N];
        logic [BYTE_COUNT_WIDTH-1:0] bytes_read[N];
        logic [BYTE_COUNT_WIDTH-1:0] bytes_written[N];
        logic [N-1:0] data_empty;
        logic [N-1:0] data_ready;
        logic [N-1:0] data_valid;
        logic [N-1:0] data_pop;
        logic [N-1:0] data_push;
        logic [N-1:0] load_armed;
        logic [N-1:0] store_armed;
        logic [N-1:0] load_finished;
        logic [N-1:0] store_finished;
        logic [N-1:0] event_satisfied;
        logic [COMPLETION_BITS-1:0] completion_input;
        logic [COMPLETION_BITS-1:0] completion_output;
        logic [EVENT_BITS-1:0] event_input;
        logic [EVENT_BITS-1:0] event_output;
        logic completion_in_ready;
        logic completion_fifo_valid;
        logic completion_empty;
        logic event_in_ready;
        logic event_fifo_valid;
        logic event_empty;
        wire controls_known = ( ^ {i_drain, i_flush, i_error_clear, i_region_valid, i_command_valid,
            i_cancel_valid, i_completion_ready, i_event_ready} !== 1'bx);
        wire run_enable = (i_rstb === 1'b1) && controls_known && (i_flush === 1'b0) &&!flushing;
        wire flush_start = (i_rstb === 1'b1) && (i_flush === 1'b1) &&!flush_seen &&!flushing;
        wire discard = flushing || (i_flush === 1'b1);
        wire all_queues_empty = ( | queue_valid) == 0 && ( & data_empty) && completion_empty &&
            event_empty;
        wire all_channels_idle = ( | o_channel_busy) == 0;
        wire core_idle = all_queues_empty && all_channels_idle &&!flushing;
        wire region_accept = o_region_ready && (i_region_valid === 1'b1);
        wire command_accept = o_command_ready && (i_command_valid === 1'b1);
        wire cancel_accept = o_cancel_ready && (i_cancel_valid === 1'b1);
        wire channel_known = ( ^ i_command_channel !== 1'bx) && (32'(i_command_channel) < N);
        wire cancel_channel_known = ( ^ i_cancel_channel !== 1'bx) && (32'(i_cancel_channel) < N);
        wire region_index_known = ( ^ i_region_index !== 1'bx) && (32'(i_region_index) < R);
        logic region_legal;
        logic [4:0] validation_error;
        wire uses_source = i_command_mode == DMA_MEMORY_TO_MEMORY || i_command_mode ==
            DMA_MEMORY_TO_STREAM;
        wire uses_destination = i_command_mode == DMA_MEMORY_TO_MEMORY || i_command_mode ==
            DMA_STREAM_TO_MEMORY;
        wire source_legal;
        wire destination_legal;
        wire [4:0] source_bounds_error;
        wire [4:0] destination_error;
        wire [W:0] source_low;
        wire [W:0] source_limit;
        wire [W:0] destination_low;
        wire [W:0] destination_limit;
        wire [C-1:0] validation_inner_count;
        wire [C-1:0] validation_outer_count;
        wire [SIZE_WIDTH-1:0] validation_size;
        wire [2*C-1:0] element_count =
            (2 * C)'(validation_inner_count) * (2 * C)'(validation_outer_count);
        wire [BYTE_COUNT_WIDTH-1:0] byte_count =
            BYTE_COUNT_WIDTH'(element_count) << validation_size;
        logic source_permission;
        logic destination_permission;
        logic duplicate;
        wire unsupported_burst;
        wire unsupported_size;
        if (MAX_BURST_BEATS == 2 ** BURST_WIDTH - 1) begin : g_all_bursts
            assign unsupported_burst = 1'b0;
        end else begin : g_limit_burst
            assign unsupported_burst = i_command_max_burst_beats > BURST_WIDTH'(MAX_BURST_BEATS);
        end
        if (MAX_ELEMENT_BYTES_LOG2 == 2 ** SIZE_WIDTH - 1) begin : g_all_sizes
            assign unsupported_size = 1'b0;
        end else begin : g_limit_size
            assign unsupported_size = 32'(i_command_element_size_log2) > MAX_ELEMENT_BYTES_LOG2;
        end
        wire unknown_command_channel = (i_command_valid === 1'b1) &&!channel_known;
        wire unknown_cancel_channel = (i_cancel_valid === 1'b1) &&!cancel_channel_known;
        wire [N-1:0] queue_push;
        wire [N-1:0] unused_completion_grant;
        wire [N-1:0] unused_event_grant;
        wire [CHANNEL_WIDTH-1:0] completion_index;
        wire [CHANNEL_WIDTH-1:0] event_index;
        wire completion_grant;
        wire event_grant;
        wire completion_take;
        wire event_take;
        wire [N-1:0] completion_eligible;
        wire [N-1:0] event_request;
        wire completion_arb_error;
        wire event_arb_error;
        wire [7:0] unused_global_fifo_status;
        wire [$clog2(CQ+1)-1:0] unused_completion_occupancy;
        wire [$clog2(EQ+1)-1:0] unused_event_occupancy;
        wire [9:0] unused_arb_status;
        wire [2*CHANNEL_WIDTH-1:0] unused_arb_owners;

        assign o_descriptor_epoch = epoch;
        assign o_error_code = engine_error;
        assign o_error = engine_error != DMA_ERR_NONE;
        assign o_fatal_error = fatal_error;
        assign o_idle = (i_rstb === 1'b1) && core_idle;
        assign o_quiescent = run_enable && core_idle && (i_drain === 1'b0) &&!command_accept
            &&!cancel_accept;
        assign o_drain_done = (i_rstb === 1'b1) && (i_drain === 1'b1) && core_idle;
        assign o_region_ready = run_enable && core_idle && (i_drain === 1'b0) && (i_error_clear ===
            1'b0) &&!fatal_error;
        assign o_cancel_ready = run_enable && (SUPPORT_CANCELLATION == 1) && cancel_channel_known
            && ( ^ {i_cancel_context_id, i_cancel_command_id} !== 1'bx) &&!fatal_error;

        always_comb begin
            o_command_ready = 1'b0;

            if (run_enable &&!fatal_error && i_drain === 1'b0 &&!region_accept &&
                !(core_idle && i_error_clear === 1'b1) && channel_known)
                o_command_ready = queue_ready[i_command_channel];

            region_legal = 1'b0;

            if (region_index_known && ( ^ {i_region_enable, i_region_space_id, i_region_base,
                i_region_limit,
                i_region_context_id, i_region_read_enable, i_region_write_enable} !== 1'bx))
                region_legal =!i_region_enable || (i_region_limit > {1'b0, i_region_base} &&
                    i_region_limit <= ({1'b1, {W{1'b0}}}) && (i_region_read_enable ||
                        i_region_write_enable));
        end

        // Quiet the count multiplier and byte-count shifter between command
        // handshakes, even if an inactive producer toggles descriptor inputs.
        operand_isolation #(
            .WIDTH(2 * C + SIZE_WIDTH)
        ) u_command_arithmetic_input (
            .i_data({i_command_inner_count, i_command_outer_count, i_command_element_size_log2}),
            .i_isolate(!command_accept),
            .o_data({validation_inner_count, validation_outer_count, validation_size})
        );

        dma_engine_bounds #(
            .W(W),
            .C(C),
            .SIZE_WIDTH(SIZE_WIDTH),
            .MAX_ELEMENT_LOG2(MAX_ELEMENT_BYTES_LOG2)
        ) u_source_bounds (
            .i_enable(command_accept && uses_source),
            .i_mode(i_command_address_mode),
            .i_base(i_command_source_base),
            .i_inner_stride(i_command_source_inner_stride),
            .i_outer_stride(i_command_source_outer_stride),
            .i_inner_count(i_command_inner_count),
            .i_outer_count(i_command_outer_count),
            .i_size(i_command_element_size_log2),
            .o_legal(source_legal),
            .o_error(source_bounds_error),
            .o_lowest(source_low),
            .o_limit(source_limit)
        );

        dma_engine_bounds #(
            .W(W),
            .C(C),
            .SIZE_WIDTH(SIZE_WIDTH),
            .MAX_ELEMENT_LOG2(MAX_ELEMENT_BYTES_LOG2)
        ) u_destination_bounds (
            .i_enable(command_accept && uses_destination),
            .i_mode(i_command_address_mode),
            .i_base(i_command_destination_base),
            .i_inner_stride(i_command_destination_inner_stride),
            .i_outer_stride(i_command_destination_outer_stride),
            .i_inner_count(i_command_inner_count),
            .i_outer_count(i_command_outer_count),
            .i_size(i_command_element_size_log2),
            .o_legal(destination_legal),
            .o_error(destination_error),
            .o_lowest(destination_low),
            .o_limit(destination_limit)
        );

        always_comb begin
            source_permission = 1'b0;
            destination_permission = 1'b0;
            duplicate = 1'b0;

            if (command_accept && ( ^ i_command_source_region !== 1'bx) &&
                32'(i_command_source_region) < R) begin
                source_permission = region_enabled[i_command_source_region] &&
                    region_read[i_command_source_region] &&
                    region_space[i_command_source_region] === i_command_source_space &&
                        region_context[i_command_source_region] === i_command_context_id &&
                    source_low >= {1'b0, region_base[i_command_source_region]} && source_limit <=
                        region_limit[i_command_source_region];
            end

            if (command_accept && ( ^ i_command_destination_region !== 1'bx) &&
                32'(i_command_destination_region) < R) begin
                destination_permission = region_enabled[i_command_destination_region] &&
                    region_write[i_command_destination_region] &&
                    region_space[i_command_destination_region] === i_command_destination_space &&
                        region_context[i_command_destination_region] === i_command_context_id &&
                    destination_low >= {1'b0, region_base[i_command_destination_region]} &&
                        destination_limit <= region_limit[i_command_destination_region];
            end

            if (command_accept && channel_known)
                duplicate = queue_duplicate[i_command_channel] ||
                ((phase[i_command_channel] != DMA_IDLE) && active_context[i_command_channel] ===
                    i_command_context_id &&
                    active_id[i_command_channel] === i_command_id);

            validation_error = DMA_ERR_NONE;

            if (command_accept) begin
                if (( ^ {i_command_mode, i_command_address_mode, i_command_inner_count,
                    i_command_outer_count,
                    i_command_element_size_log2, i_command_stream_id, i_command_context_id,
                        i_command_id, i_command_priority,
                    i_command_start_mode, i_command_completion_event_enable,
                        i_command_max_burst_beats} === 1'bx))
                    validation_error = DMA_ERR_UNKNOWN;
                else if (i_command_mode == 3 || i_command_address_mode == 3 || i_command_inner_count
                    == 0 || i_command_outer_count == 0 ||
                    (i_command_address_mode != 2 && i_command_outer_count != 1) || unsupported_size)
                    validation_error = DMA_ERR_COMMAND;
                else if ((i_command_mode != DMA_MEMORY_TO_MEMORY) && ( ^ i_command_stream_last ===
                    1'bx))
                    validation_error = DMA_ERR_UNKNOWN;
                else if (i_command_start_mode == 3 || ((SUPPORT_EVENT_START == 0) &&
                    i_command_start_mode != DMA_START_IMMEDIATE) ||
                    ((i_command_start_mode != DMA_START_IMMEDIATE) && (( ^
                        i_command_start_event_mask === 1'bx) || i_command_start_event_mask == 0)) ||
                    (i_command_completion_event_enable && (( ^ i_command_completion_event_id ===
                        1'bx) || 32'(i_command_completion_event_id) >= V)))
                    validation_error = DMA_ERR_EVENT;
                else if (i_command_max_burst_beats == 0 || unsupported_burst)
                    validation_error = DMA_ERR_BURST;
                else if (uses_source &&!source_legal) validation_error = source_bounds_error;
                else if (uses_destination &&!destination_legal)
                    validation_error = destination_error;
                else if ((uses_source &&!source_permission) || (uses_destination
                    &&!destination_permission))
                    validation_error = DMA_ERR_PERMISSION;
                else if (duplicate) validation_error = DMA_ERR_DUPLICATE;
                else if (i_command_mode == DMA_MEMORY_TO_MEMORY && i_command_source_space ==
                    i_command_destination_space &&
                    source_low < destination_limit && destination_low < source_limit)
                    validation_error = DMA_ERR_OVERLAP;
            end

            // Normalize every ignored field before parity-protected storage.
            command = '0;

            if (command_accept && validation_error == DMA_ERR_NONE) begin
                command.mode = i_command_mode;
                command.address_mode = i_command_address_mode;
                command.start_mode = i_command_start_mode;
                command.inner_count = i_command_inner_count;
                command.outer_count = i_command_outer_count;
                command.size = i_command_element_size_log2;
                command.context_id = i_command_context_id;
                command.command_id = i_command_id;
                command.stream_id = i_command_stream_id;
                command.priority_hint = i_command_priority;
                command.burst = i_command_max_burst_beats;
                command.elements = element_count;
                command.bytes = byte_count;
                command.event_enable = i_command_completion_event_enable;
                if (i_command_completion_event_enable)
                    command.event_id = i_command_completion_event_id;
                if (i_command_start_mode != DMA_START_IMMEDIATE)
                    command.event_mask = i_command_start_event_mask;
                if (i_command_mode != DMA_MEMORY_TO_MEMORY)
                    command.stream_last = i_command_stream_last;
                if (uses_source) begin
                    command.source_base = i_command_source_base;
                    command.source_space = i_command_source_space;
                    command.source_region = i_command_source_region;
                    if (i_command_address_mode != 0)
                        command.source_inner = i_command_source_inner_stride;
                    if (i_command_address_mode == 2)
                        command.source_outer = i_command_source_outer_stride;
                end
                if (uses_destination) begin
                    command.destination_base = i_command_destination_base;
                    command.destination_space = i_command_destination_space;
                    command.destination_region = i_command_destination_region;
                    if (i_command_address_mode != 0)
                        command.destination_inner = i_command_destination_inner_stride;
                    if (i_command_address_mode == 2)
                        command.destination_outer = i_command_destination_outer_stride;
                end
            end
        end

        // Independent registered output queues. Both records enter atomically;
        // the event arbiter services the selected completion's one-hot request.
        for (genvar c = 0; c < N; c ++ ) begin : g_retirement
            command_t owner;
            assign owner = active_packet[c];
            wire [COMMAND_BITS-1:0] unused_owner_fields = owner;
            assign active_context[c] = owner.context_id;
            assign active_id[c] = owner.command_id;
            assign active_event_id[c] = owner.event_id;
            assign completion_pending[c] = phase[c] == DMA_COMPLETE;
            assign completion_eligible[c] =!owner.event_enable || event_in_ready;
            assign event_request[c] = completion_grant && completion_index == CHANNEL_WIDTH'(c) &&
                owner.event_enable;
            assign retire[c] = completion_take && completion_index == CHANNEL_WIDTH'(c);
        end

        round_robin_arbiter #(
            .NUM_REQUESTERS(N),
            .HAS_LOCK(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_completion_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_request(completion_pending),
            .i_eligible(completion_eligible),
            .i_lock({N{1'b0}}),
            .i_accept(completion_take),
            .i_flush(discard),
            .o_grant_valid(completion_grant),
            .o_grant_onehot(unused_completion_grant),
            .o_grant_index(completion_index),
            .o_grant_lock(unused_arb_status[0]),
            .o_grant_accepted(unused_arb_status[1]),
            .o_contended(unused_arb_status[2]),
            .o_pending(unused_arb_status[3]),
            .o_locked(unused_arb_status[8]),
            .o_lock_owner(unused_arb_owners[0+:CHANNEL_WIDTH]),
            .o_protocol_error(completion_arb_error)
        );

        round_robin_arbiter #(
            .NUM_REQUESTERS(N),
            .HAS_LOCK(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_event_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_request(event_request),
            .i_eligible({N{1'b1}}),
            .i_lock({N{1'b0}}),
            .i_accept(event_take),
            .i_flush(discard),
            .o_grant_valid(event_grant),
            .o_grant_onehot(unused_event_grant),
            .o_grant_index(event_index),
            .o_grant_lock(unused_arb_status[4]),
            .o_grant_accepted(unused_arb_status[5]),
            .o_contended(unused_arb_status[6]),
            .o_pending(unused_arb_status[7]),
            .o_locked(unused_arb_status[9]),
            .o_lock_owner(unused_arb_owners[CHANNEL_WIDTH+:CHANNEL_WIDTH]),
            .o_protocol_error(event_arb_error)
        );

        assign completion_take = run_enable && completion_grant && completion_in_ready &&
            (!event_request[completion_index] || (event_grant && event_in_ready));
        assign event_take = completion_take && event_grant;

        always_comb begin
            completion_record = '0;
            event_record = '0;

            if (completion_grant) begin
                completion_record.channel = completion_index;
                completion_record.context_id = active_context[completion_index];
                completion_record.command_id = active_id[completion_index];
                completion_record.status = result_status[completion_index];
                completion_record.bytes_read = bytes_read[completion_index];
                completion_record.bytes_written = bytes_written[completion_index];
                completion_record.error_code = command_error[completion_index];
            end

            if (event_grant) begin
                event_record.id = active_event_id[event_index];
                event_record.context_id = active_context[event_index];
                event_record.command_id = active_id[event_index];
                event_record.error = result_status[event_index] != DMA_SUCCESS;
            end

            completion_input = completion_record;
            event_input = event_record;
        end

        fifo #(
            .DATA_WIDTH(COMPLETION_BITS),
            .DEPTH(CQ),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_completion_fifo (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_valid(completion_take),
            .o_ready(completion_in_ready),
            .i_data(completion_input),
            .o_valid(completion_fifo_valid),
            .i_ready(discard || (run_enable && i_completion_ready === 1'b1)),
            .o_data(completion_output),
            .o_full(unused_global_fifo_status[0]),
            .o_empty(completion_empty),
            .o_almost_full(unused_global_fifo_status[1]),
            .o_almost_empty(unused_global_fifo_status[2]),
            .o_occupancy(unused_completion_occupancy)
        );

        fifo #(
            .DATA_WIDTH(EVENT_BITS),
            .DEPTH(EQ),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_event_fifo (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_valid(event_take),
            .o_ready(event_in_ready),
            .i_data(event_input),
            .o_valid(event_fifo_valid),
            .i_ready(discard || (run_enable && i_event_ready === 1'b1)),
            .o_data(event_output),
            .o_full(unused_global_fifo_status[3]),
            .o_empty(event_empty),
            .o_almost_full(unused_global_fifo_status[4]),
            .o_almost_empty(unused_global_fifo_status[5]),
            .o_occupancy(unused_event_occupancy)
        );

        assign unused_global_fifo_status[7:6] = '0;
        assign o_completion_valid = run_enable && completion_fifo_valid;
        assign o_event_valid = run_enable && event_fifo_valid;

        operand_isolation #(
            .WIDTH(COMPLETION_BITS)
        ) u_completion_output (
            .i_data(completion_output),
            .i_isolate(!o_completion_valid),
            .o_data({
                o_completion_channel,
                o_completion_context_id,
                o_completion_command_id,
                o_completion_status,
                o_completion_bytes_read,
                o_completion_bytes_written,
                o_completion_error_code
            })
        );

        operand_isolation #(
            .WIDTH(EVENT_BITS)
        ) u_event_output (
            .i_data(event_output),
            .i_isolate(!o_event_valid),
            .o_data({o_event_id, o_event_context_id, o_event_command_id, o_event_error})
        );

        for (genvar c = 0; c < N; c ++ ) begin : g_channel
            command_t head;
            command_t owner;
            wire [COMMAND_BITS-1:0] queued_word;
            assign head = queued_word;
            wire [COMMAND_BITS-1:0] unused_head_fields = head;
            assign owner = active_packet[c];
            wire [COMMAND_BITS-1:0] unused_owner_fields = owner;
            logic [2*C-1:0] source_count;
            logic [2*C-1:0] destination_count;
            logic [TIMEOUT_WIDTH-1:0] transfer_timer;
            logic [CANCEL_TIMEOUT_WIDTH-1:0] cancel_timer;
            logic [BEAT_BITS-1:0] data_input;
            logic [BEAT_BITS-1:0] data_output;
            logic [D-1:0] source_data;
            logic [D-1:0] clean_data;
            logic [D-1:0] fifo_data;
            logic [DATA_BYTES-1:0] source_keep;
            logic [DATA_BYTES-1:0] expected_keep;
            logic [DATA_BYTES-1:0] fifo_keep;
            logic source_first;
            logic source_last;
            logic source_error;
            logic fifo_first;
            logic fifo_last;
            logic fifo_error;
            logic [X-1:0] fifo_context;
            logic [I-1:0] fifo_stream;
            logic [J-1:0] fifo_id;
            logic [EP-1:0] fifo_epoch;
            logic source_valid;
            logic source_legal_beat;
            logic source_take;
            logic sink_take;
            logic framing_error;
            logic upstream_error;
            logic backend_fault;
            logic protocol_fault;
            logic [4:0] new_error;
            logic [4:0] reported_error;
            assign local_error[c] = reported_error;
            logic has_load;
            logic has_store;
            wire running = phase[c] == DMA_RUN;
            wire arming = phase[c] == DMA_ARM_STORE || phase[c] == DMA_ARM_LOAD;
            wire executing = arming || running;
            wire canceling = phase[c] == DMA_CANCEL || phase[c] == DMA_FATAL;
            wire load_config_take = o_load_config_valid[c] && i_load_config_ready[c] === 1'b1;
            wire store_config_take = o_store_config_valid[c] && i_store_config_ready[c] === 1'b1;
            wire matching_load_done = run_enable && (i_load_done[c] === 1'b1) &&
                (i_load_done_epoch[c*EP+:EP] === epoch) && load_armed[c];
            wire matching_store_done = run_enable && (i_store_done[c] === 1'b1) &&
                (i_store_done_epoch[c*EP+:EP] === epoch) && store_armed[c];
            wire stale_load = (i_load_done[c] === 1'b1 && i_load_done_epoch[c*EP+:EP] !== epoch)
                ||
                (i_load_stream_valid[c] === 1'b1 && i_load_stream_epoch[c*EP+:EP] !== epoch);
            wire stale_store = i_store_done[c] === 1'b1 && i_store_done_epoch[c*EP+:EP] !==
                epoch;
            // A normal done concurrent with flush acceptance already proves that
            // peer is idle. Capture it before the flush advances the epoch;
            // later old-epoch done pulses remain stale and cannot release it.
            wire flush_load_done = flush_start && load_armed[c] && i_load_done[c] === 1'b1 &&
                i_load_done_epoch[c*EP+:EP] === epoch;
            wire flush_store_done = flush_start && store_armed[c] && i_store_done[c] === 1'b1 &&
                i_store_done_epoch[c*EP+:EP] === epoch;
            wire all_cancel_done = (!load_armed[c] || load_finished[c] || flush_load_done ||
                i_load_cancel_done[c] === 1'b1) &&
                (!store_armed[c] || store_finished[c] || flush_store_done ||
                    i_store_cancel_done[c] === 1'b1);
            wire [BYTE_COUNT_WIDTH-1:0] element_bytes = BYTE_COUNT_WIDTH'(1) << owner.size;
            wire [BYTE_COUNT_WIDTH-1:0] handed_bytes = (BYTE_COUNT_WIDTH'(destination_count) +
                BYTE_COUNT_WIDTH'(sink_take)) << owner.size;
            wire [BYTE_COUNT_WIDTH-1:0] committed =
                i_store_bytes_committed[c*BYTE_COUNT_WIDTH+:BYTE_COUNT_WIDTH];
            wire committed_legal = ( ^ committed !== 1'bx) && committed <= handed_bytes;
            wire source_finished = (source_count + (2 * C)'(source_take)) == owner.elements;
            wire destination_finished = (destination_count + (2 * C)'(sink_take)) == owner.elements;
            wire successful = running && source_finished && destination_finished &&
                (!has_load || load_finished[c] || matching_load_done) &&
                (!has_store || ((store_finished[c] || matching_store_done) && committed_legal &&
                    committed == owner.bytes)) &&
                (owner.mode != DMA_MEMORY_TO_MEMORY || (data_empty[c] &&!data_push[c]) ||
                    (data_pop[c] &&
                        o_data_fifo_occupancy[c*DATA_OCCUPANCY_WIDTH+:DATA_OCCUPANCY_WIDTH] ==
                        DATA_OCCUPANCY_WIDTH'(1) &&!data_push[c]));
            wire timer_expired = executing && transfer_timer ==
                TIMEOUT_WIDTH'(TRANSFER_TIMEOUT_CYCLES - 1);
            wire cancel_expired = phase[c] == DMA_CANCEL && cancel_timer ==
                CANCEL_TIMEOUT_WIDTH'(CANCEL_TIMEOUT_CYCLES - 1);
            wire start = queue_pop[c] &&!discard;
            wire active_match = phase[c] != DMA_IDLE && phase[c] != DMA_CANCEL && phase[c] !=
                DMA_FATAL && phase[c] != DMA_COMPLETE &&
                owner.context_id === i_cancel_context_id &&
                    owner.command_id === i_cancel_command_id;
            wire [8:0] unused_status;

            assign o_channel_busy[c] = phase[c] != DMA_IDLE;
            assign o_channel_canceling[c] = canceling;
            assign has_load = owner.mode != DMA_STREAM_TO_MEMORY;
            assign has_store = owner.mode != DMA_MEMORY_TO_STREAM;
            assign active_cancel[c] = cancel_accept && i_cancel_channel == CHANNEL_WIDTH'(c) &&
                active_match;
            assign queue_cancel[c] = cancel_accept && i_cancel_channel == CHANNEL_WIDTH'(c)
                &&!active_match;
            assign queue_push[c] = command_accept && validation_error == DMA_ERR_NONE &&
                i_command_channel == CHANNEL_WIDTH'(c);
            assign event_satisfied[c] = head.start_mode == DMA_START_IMMEDIATE
                ||
                (( ^ i_event_pending !== 1'bx) && ((head.start_mode ==
                    DMA_START_EVENT_OR && ( | (head.event_mask &
                    i_event_pending))) ||
                    (head.start_mode == DMA_START_EVENT_AND &&
                        ((head.event_mask & i_event_pending) ==
                        head.event_mask))));
            assign queue_pop[c] = run_enable &&!fatal_error && phase[c] == DMA_IDLE &&
                queue_valid[c] &&
                !queue_corrupt[c] &&!protocol_fault &&!queue_cancel[c] && (queue_canceled[c] ||
                    event_satisfied[c]);
            assign o_event_command_stall[c] = run_enable && queue_valid[c] &&!queue_pop[c]
                &&!queue_canceled[c] && event_satisfied[c];
            assign o_event_data_stall[c] = run_enable && running &&
                ((source_valid &&!source_take) || (owner.mode ==
                    DMA_MEMORY_TO_MEMORY && data_valid[c] &&!sink_take));

            dma_engine_command_queue #(
                .DATA_BITS(COMMAND_BITS),
                .DEPTH(Q),
                .ID_BITS(J),
                .CONTEXT_BITS(X),
                .PROTECTED(PROTECT_COMMAND_FIFO != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_commands (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_flush(discard),
                .i_valid(queue_push[c]),
                .o_ready(queue_ready[c]),
                .i_data(command),
                .i_id(i_command_id),
                .i_context(i_command_context_id),
                .i_query_id(i_command_id),
                .i_query_context(i_command_context_id),
                .o_duplicate(queue_duplicate[c]),
                .i_cancel(queue_cancel[c]),
                .i_cancel_id(i_cancel_command_id),
                .i_cancel_context(i_cancel_context_id),
                .o_cancel_match(queue_cancel_match[c]),
                .o_valid(queue_valid[c]),
                .i_ready(queue_pop[c]),
                .o_data(queued_word),
                .o_canceled(queue_canceled[c]),
                .o_corrupt(queue_corrupt[c]),
                .o_occupancy(
                    o_command_occupancy[c*COMMAND_OCCUPANCY_WIDTH+:COMMAND_OCCUPANCY_WIDTH])
            );

            // Every backend field is clamped when its descriptor is not valid.
            assign o_load_config_valid[c] = run_enable && phase[c] == DMA_ARM_LOAD
                &&!active_cancel[c];
            assign o_store_config_valid[c] = run_enable && phase[c] == DMA_ARM_STORE
                &&!active_cancel[c];
            assign o_load_cancel[c] = (i_rstb === 1'b1) && (canceling || discard) && load_armed[c]
                &&!load_finished[c];
            assign o_store_cancel[c] = (i_rstb === 1'b1) && (canceling || discard) && store_armed[c]
                &&!store_finished[c];

            operand_isolation #(
                .WIDTH(2 + W + SIZE_WIDTH + 2 * C + 2 * W + S + X + I + BURST_WIDTH + P + EP)
            ) u_load_descriptor (
                .i_data({
                    owner.address_mode,
                    owner.source_base,
                    owner.size,
                    owner.inner_count,
                    owner.outer_count,
                    owner.source_inner,
                    owner.source_outer,
                    owner.source_space,
                    owner.context_id,
                    owner.stream_id,
                    owner.burst,
                    owner.priority_hint,
                    epoch
                }),
                .i_isolate(!o_load_config_valid[c]),
                .o_data({
                    o_load_mode[c*2+:2],
                    o_load_base_address[c*W+:W],
                    o_load_element_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH],
                    o_load_inner_count[c*C+:C],
                    o_load_outer_count[c*C+:C],
                    o_load_inner_stride[c*W+:W],
                    o_load_outer_stride[c*W+:W],
                    o_load_space_id[c*S+:S],
                    o_load_context_id[c*X+:X],
                    o_load_channel_id[c*I+:I],
                    o_load_max_burst_beats[c*BURST_WIDTH+:BURST_WIDTH],
                    o_load_priority[c*P+:P],
                    o_load_descriptor_epoch[c*EP+:EP]
                })
            );

            operand_isolation #(
                .WIDTH(2 + W + SIZE_WIDTH + 2 * C + 2 * W + S + X + I + BURST_WIDTH + P + EP)
            ) u_store_descriptor (
                .i_data({
                    owner.address_mode,
                    owner.destination_base,
                    owner.size,
                    owner.inner_count,
                    owner.outer_count,
                    owner.destination_inner,
                    owner.destination_outer,
                    owner.destination_space,
                    owner.context_id,
                    owner.stream_id,
                    owner.burst,
                    owner.priority_hint,
                    epoch
                }),
                .i_isolate(!o_store_config_valid[c]),
                .o_data({
                    o_store_mode[c*2+:2],
                    o_store_base_address[c*W+:W],
                    o_store_element_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH],
                    o_store_inner_count[c*C+:C],
                    o_store_outer_count[c*C+:C],
                    o_store_inner_stride[c*W+:W],
                    o_store_outer_stride[c*W+:W],
                    o_store_space_id[c*S+:S],
                    o_store_context_id[c*X+:X],
                    o_store_channel_id[c*I+:I],
                    o_store_max_burst_beats[c*BURST_WIDTH+:BURST_WIDTH],
                    o_store_priority[c*P+:P],
                    o_store_descriptor_epoch[c*EP+:EP]
                })
            );

            always_comb begin
                source_valid = 1'b0;
                source_data = '0;
                source_keep = '0;
                source_first = 1'b0;
                source_last = 1'b0;
                source_error = 1'b0;
                expected_keep = DATA_BYTES'(((DATA_BYTES + 1)'(1) << (1 << owner.size)) - 1'b1);
                source_legal_beat = 1'b0;
                framing_error = 1'b0;

                if (running && run_enable &&!active_cancel[c]) begin
                    if (owner.mode == DMA_STREAM_TO_MEMORY) begin
                        source_valid = i_stream_valid[c] === 1'b1;
                        source_data = i_stream_data[c*D+:D];
                        source_keep = i_stream_keep[c*DATA_BYTES+:DATA_BYTES];
                        source_first = i_stream_first[c];
                        source_last = i_stream_descriptor_last[c];
                        source_error = i_stream_error[c];
                        source_legal_beat = ( ^ {source_keep, source_first, source_last,
                            i_stream_last[c], source_error,
                            i_stream_id[c*I+:I], i_stream_context_id[c*X+:X]} !== 1'bx) &&
                            i_stream_id[c*I+:I] === owner.stream_id &&
                                i_stream_context_id[c*X+:X] === owner.context_id &&
                            i_stream_last[c] === ((source_count == owner.elements - 1'b1) &&
                                owner.stream_last);
                    end else begin
                        source_valid = (i_load_stream_valid[c] === 1'b1) &&
                            i_load_stream_epoch[c*EP+:EP] === epoch;
                        source_data = i_load_stream_data[c*D+:D];
                        source_keep = i_load_stream_keep[c*DATA_BYTES+:DATA_BYTES];
                        source_first = i_load_stream_first[c];
                        source_last = i_load_stream_last[c];
                        source_error = i_load_stream_error[c];
                        source_legal_beat = ( ^ {source_keep, source_first, source_last,
                            source_error} !== 1'bx);
                    end

                    source_legal_beat = source_legal_beat && source_count <
                        owner.elements &&
                        source_first === (source_count == 0) && source_last === (source_count ==
                            owner.elements - 1'b1) && source_keep ===
                            expected_keep;
                    framing_error = source_valid &&!source_legal_beat;
                end

                clean_data = '0;

                for (int b = 0; b < DATA_BYTES; b ++ )
                if (source_keep[b] === 1'b1) clean_data[b*8+:8] = source_data[b*8+:8];
            end

            assign data_input = {
                clean_data,
                source_keep,
                source_first,
                source_last,
                source_error,
                owner.context_id,
                owner.stream_id,
                owner.command_id,
                epoch
            };
            assign {fifo_data, fifo_keep, fifo_first, fifo_last, fifo_error, fifo_context,
                fifo_stream, fifo_id, fifo_epoch} = data_output;
            assign data_push[c] = running && run_enable &&!active_cancel[c] &&
                owner.mode == DMA_MEMORY_TO_MEMORY && source_valid &&
                source_legal_beat;

            fifo #(
                .DATA_WIDTH(BEAT_BITS),
                .DEPTH(DQ),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_data_fifo (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_valid(data_push[c]),
                .o_ready(data_ready[c]),
                .i_data(data_input),
                .o_valid(data_valid[c]),
                .i_ready(data_pop[c] || discard || canceling),
                .o_data(data_output),
                .o_full(unused_status[0]),
                .o_empty(data_empty[c]),
                .o_almost_full(unused_status[1]),
                .o_almost_empty(unused_status[2]),
                .o_occupancy(o_data_fifo_occupancy[c*DATA_OCCUPANCY_WIDTH+:DATA_OCCUPANCY_WIDTH])
            );

            assign o_load_stream_ready[c] = running && run_enable &&!active_cancel[c] && has_load
                && source_legal_beat &&
                (i_load_stream_valid[c] === 1'b0 || (i_load_stream_valid[c] === 1'b1 &&
                    i_load_stream_epoch[c*EP+:EP] === epoch)) &&
                (owner.mode == DMA_MEMORY_TO_MEMORY ? data_ready[c] :
                    (i_stream_ready[c] === 1'b1));
            assign o_stream_ready[c] = running && run_enable &&!active_cancel[c] &&
                owner.mode == DMA_STREAM_TO_MEMORY &&
                source_legal_beat && (i_store_stream_ready[c] === 1'b1);
            assign o_stream_valid[c] = running && run_enable &&!active_cancel[c] &&
                owner.mode == DMA_MEMORY_TO_STREAM && source_valid &&
                source_legal_beat;
            assign o_store_stream_valid[c] = running && run_enable &&!active_cancel[c] &&
                has_store &&
                (owner.mode == DMA_MEMORY_TO_MEMORY ? (data_valid[c] &&
                    fifo_epoch === epoch && fifo_context === owner.context_id
                    && fifo_stream === owner.stream_id && fifo_id ===
                    owner.command_id) : (source_valid && source_legal_beat));
            assign data_pop[c] = o_store_stream_valid[c] && owner.mode ==
                DMA_MEMORY_TO_MEMORY && (i_store_stream_ready[c] === 1'b1);
            assign source_take = owner.mode == DMA_STREAM_TO_MEMORY ?
                (o_stream_ready[c] && source_valid) : (o_load_stream_ready[c] && source_valid);
            assign sink_take = owner.mode == DMA_MEMORY_TO_STREAM ?
                (o_stream_valid[c] && i_stream_ready[c] === 1'b1)
                : (o_store_stream_valid[c] && i_store_stream_ready[c] === 1'b1);

            operand_isolation #(
                .WIDTH(D + DATA_BYTES + 4 + I + X)
            ) u_stream_output (
                .i_data({
                    clean_data,
                    source_keep,
                    source_first,
                    source_last,
                    (source_last && owner.stream_last),
                    owner.stream_id,
                    owner.context_id,
                    source_error
                }),
                .i_isolate(!o_stream_valid[c]),
                .o_data({
                    o_stream_data[c*D+:D],
                    o_stream_keep[c*DATA_BYTES+:DATA_BYTES],
                    o_stream_first[c],
                    o_stream_descriptor_last[c],
                    o_stream_last[c],
                    o_stream_id[c*I+:I],
                    o_stream_context_id[c*X+:X],
                    o_stream_error[c]
                })
            );

            wire [D+DATA_BYTES+2:0] store_payload = owner.mode ==
                DMA_MEMORY_TO_MEMORY
                ? {fifo_data, fifo_keep, fifo_first, fifo_last, fifo_error}
                : {clean_data, source_keep, source_first, source_last, source_error};
            operand_isolation #(
                .WIDTH(D + DATA_BYTES + 3)
            ) u_store_output (
                .i_data(store_payload),
                .i_isolate(!o_store_stream_valid[c]),
                .o_data({
                    o_store_stream_data[c*D+:D],
                    o_store_stream_keep[c*DATA_BYTES+:DATA_BYTES],
                    o_store_stream_first[c],
                    o_store_stream_last[c],
                    o_store_stream_error[c]
                })
            );

            always_comb begin
                protocol_fault = ( ^ {i_load_config_ready[c], i_load_config_rejected[c],
                    i_load_stream_valid[c],
                    i_load_done[c], i_load_done_error[c], i_load_cancel_done[c],
                        i_store_config_ready[c], i_store_config_rejected[c],
                    i_store_stream_ready[c], i_store_done[c], i_store_done_error[c],
                        i_store_cancel_done[c],
                    i_stream_valid[c], i_stream_ready[c]} === 1'bx);
                backend_fault = (i_load_config_rejected[c] === 1'b1) ||
                    (i_store_config_rejected[c] === 1'b1) ||
                    (matching_load_done &&!i_load_done_error[c] && (!source_finished ||
                        load_finished[c])) ||
                    (matching_store_done &&!i_store_done_error[c] && (!destination_finished ||
                        store_finished[c])) ||
                    (matching_store_done &&!committed_legal) ||
                    (!discard && i_load_stream_valid[c] === 1'b1 && i_load_stream_epoch[c*EP+:EP]
                        === epoch &&!load_armed[c] &&!load_config_take) ||
                    (!discard && i_load_done[c] === 1'b1 && i_load_done_epoch[c*EP+:EP] ===
                        epoch &&!load_armed[c]) ||
                    (!discard && i_store_done[c] === 1'b1 && i_store_done_epoch[c*EP+:EP] ===
                        epoch &&!store_armed[c]) ||
                    (canceling && store_armed[c] && i_store_cancel_done[c] === 1'b1
                        &&!committed_legal);
                upstream_error = source_take && source_error;
                new_error = DMA_ERR_NONE;

                if (executing) begin
                    if (backend_fault) new_error = DMA_ERR_BACKEND;
                    else if (protocol_fault) new_error = DMA_ERR_PROTOCOL;
                    else if (framing_error) new_error = DMA_ERR_FRAMING;
                    else if (upstream_error || (matching_load_done && i_load_done_error[c]))
                        new_error = DMA_ERR_SOURCE;
                    else if (matching_store_done && i_store_done_error[c])
                        new_error = DMA_ERR_WRITE;
                end

                reported_error = new_error;

                if (reported_error == DMA_ERR_NONE && timer_expired &&!successful
                    &&!active_cancel[c])
                    reported_error = DMA_ERR_TIMEOUT;
                if (reported_error == DMA_ERR_NONE && (stale_load || stale_store))
                    reported_error = DMA_ERR_EPOCH;
                if (reported_error == DMA_ERR_NONE && protocol_fault)
                    reported_error = DMA_ERR_PROTOCOL;
                if (reported_error == DMA_ERR_NONE && backend_fault)
                    reported_error = DMA_ERR_BACKEND;
                if (queue_corrupt[c]) reported_error = DMA_ERR_PARITY;
                if (cancel_expired &&!all_cancel_done) reported_error = DMA_ERR_CANCEL_TIMEOUT;

                local_fatal[c] = queue_corrupt[c] || backend_fault || (cancel_expired
                    &&!all_cancel_done);
            end

            wire clear_transfer_timer =!executing || discard || active_cancel[c] || new_error !=
                DMA_ERR_NONE;
            wire cancel_timer_enable = phase[c] == DMA_CANCEL &&!all_cancel_done;

            counter #(
                .WIDTH(TIMEOUT_WIDTH),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_transfer_timer (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(executing && run_enable),
                .i_clear(clear_transfer_timer),
                .i_load(1'b0),
                .i_direction(1'b0),
                .i_load_value({TIMEOUT_WIDTH{1'b0}}),
                .o_count(transfer_timer),
                .o_overflow(unused_status[3]),
                .o_underflow(unused_status[4]),
                .o_terminal(unused_status[5])
            );

            counter #(
                .WIDTH(CANCEL_TIMEOUT_WIDTH),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_cancel_timer (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                // A terminal fatal state must not keep advancing this timer.
                .i_enable(cancel_timer_enable),
                .i_clear(!canceling),
                .i_load(1'b0),
                .i_direction(1'b0),
                .i_load_value({CANCEL_TIMEOUT_WIDTH{1'b0}}),
                .o_count(cancel_timer),
                .o_overflow(unused_status[6]),
                .o_underflow(unused_status[7]),
                .o_terminal(unused_status[8])
            );

            // State is reset explicitly. Descriptor payload is written only when
            // a FIFO head starts; holding phases never recapture live input ports.
            task automatic channel_update;
                if (!i_rstb) begin
                    phase[c] <= DMA_IDLE;
                    load_armed[c] <= 0;
                    store_armed[c] <= 0;
                    load_finished[c] <= 0;
                    store_finished[c] <= 0;
                    source_count <= '0;
                    destination_count <= '0;
                    bytes_read[c] <= '0;
                    bytes_written[c] <= '0;
                    command_error[c] <= DMA_ERR_NONE;
                    result_status[c] <= DMA_SUCCESS;
                    o_event_command_start[c] <= 0;
                    o_event_command_complete[c] <= 0;
                    o_event_timeout[c] <= 0;
                end else begin
                    o_event_command_start[c] <= 0;
                    o_event_command_complete[c] <= 0;
                    o_event_timeout[c] <= 0;

                    if (load_config_take) load_armed[c] <= 1;
                    if (store_config_take) store_armed[c] <= 1;
                    if (matching_load_done || flush_load_done) load_finished[c] <= 1;
                    if ((canceling || discard) && load_armed[c] && i_load_cancel_done[c] === 1'b1)
                        load_finished[c] <= 1;
                    if ((canceling || discard) && store_armed[c] && i_store_cancel_done[c] === 1'b1)
                        store_finished[c] <= 1;
                    if (flush_store_done) store_finished[c] <= 1;
                    if (matching_store_done) begin
                        store_finished[c] <= 1;

                        if (committed_legal) bytes_written[c] <= committed;
                    end

                    if (canceling && store_armed[c] && i_store_cancel_done[c] === 1'b1 &&
                        committed_legal)
                        bytes_written[c] <= committed;

                    if (discard) begin
                        // Flush suppresses ordinary completion creation. Requests
                        // stay asserted until every armed backend acknowledges.
                        if (phase[c] != DMA_IDLE && phase[c] != DMA_FATAL) begin
                            if (all_cancel_done) begin
                                phase[c] <= DMA_IDLE;
                                load_armed[c] <= 0;
                                store_armed[c] <= 0;
                            end else phase[c] <= DMA_CANCEL;
                        end

                        if (phase[c] != DMA_FATAL && cancel_expired &&!all_cancel_done) begin
                            phase[c] <= DMA_FATAL;
                            o_event_timeout[c] <= 1;
                        end
                    end else if (start) begin
                        load_armed[c] <= 0;
                        store_armed[c] <= 0;
                        load_finished[c] <= 0;
                        store_finished[c] <= 0;
                        source_count <= '0;
                        destination_count <= '0;
                        bytes_read[c] <= '0;
                        bytes_written[c] <= '0;
                        command_error[c] <= queue_canceled[c] ? DMA_ERR_CANCELED : DMA_ERR_NONE;
                        result_status[c] <= queue_canceled[c] ? DMA_CANCELED : DMA_SUCCESS;
                        o_event_command_start[c] <=!queue_canceled[c];
                        if (queue_canceled[c]) phase[c] <= DMA_COMPLETE;
                        else if (head.mode == DMA_MEMORY_TO_STREAM) phase[c] <= DMA_ARM_LOAD;
                        else phase[c] <= DMA_ARM_STORE;
                    end else if (phase[c] == DMA_FATAL) begin
                        // Fatal cancellation retains backend ownership until reset.
                    end else if (canceling) begin
                        // The deadline applies to backend acknowledgements.
                        // Discarding already-owned FIFO data may finish later.
                        if (backend_fault) phase[c] <= DMA_FATAL;
                        else if (all_cancel_done && data_empty[c]) begin
                            phase[c] <= DMA_COMPLETE;
                        end else if (cancel_expired &&!all_cancel_done) begin
                            phase[c] <= DMA_FATAL;
                            o_event_timeout[c] <= 1;
                            if (command_error[c] == DMA_ERR_NONE)
                                command_error[c] <= DMA_ERR_CANCEL_TIMEOUT;
                            result_status[c] <= DMA_ERROR;
                        end
                    end else if (executing) begin
                        if (source_take) begin
                            source_count <= source_count + 1'b1;
                            bytes_read[c] <= bytes_read[c] + element_bytes;
                        end
                        if (sink_take) begin
                            destination_count <= destination_count + 1'b1;
                            if (owner.mode == DMA_MEMORY_TO_STREAM)
                                bytes_written[c] <= bytes_written[c] + element_bytes;
                        end
                        if (active_cancel[c] || new_error != DMA_ERR_NONE ||
                            (timer_expired &&!successful)) begin
                            phase[c] <= DMA_CANCEL;
                            if (command_error[c] == DMA_ERR_NONE) begin
                                if (new_error != DMA_ERR_NONE) command_error[c] <= new_error;
                                else if (active_cancel[c]) command_error[c] <= DMA_ERR_CANCELED;
                                else command_error[c] <= DMA_ERR_TIMEOUT;
                            end
                            if (new_error == DMA_ERR_NONE && active_cancel[c])
                                result_status[c] <= DMA_CANCELED;
                            else result_status[c] <= DMA_ERROR;
                            o_event_timeout[c] <= timer_expired &&!active_cancel[c] &&
                                new_error == DMA_ERR_NONE;
                        end else if (successful) phase[c] <= DMA_COMPLETE;
                        else if (phase[c] == DMA_ARM_STORE && store_config_take) begin
                            if (owner.mode == DMA_MEMORY_TO_MEMORY) phase[c] <= DMA_ARM_LOAD;
                            else phase[c] <= DMA_RUN;
                        end else if (phase[c] == DMA_ARM_LOAD && load_config_take)
                            phase[c] <= DMA_RUN;
                    end else if (retire[c]) begin
                        phase[c] <= DMA_IDLE;
                        load_armed[c] <= 0;
                        store_armed[c] <= 0;
                        o_event_command_complete[c] <= 1;
                    end
                end
            endtask

            if (ASYNC_RESET == 1) begin : g_async
                always_ff @(posedge i_clk or negedge i_rstb) channel_update();
            end else begin : g_sync
                always_ff @(posedge i_clk) channel_update();
            end

`ifdef MOSAIC_DMA_ENGINE_ASSERTIONS
            localparam int ASSERT_DESCRIPTOR_BITS = 2 + 3 * W + SIZE_WIDTH + 2 * C + S + X + I +
                BURST_WIDTH + P + EP;
            dma_engine_assertions #(
                .C(C),
                .DESC_BITS(ASSERT_DESCRIPTOR_BITS),
                .STORE_BITS(D + DATA_BYTES + 3),
                .TILE_BITS(D + DATA_BYTES + 4 + I + X),
                .OCC_BITS(DATA_OCCUPANCY_WIDTH),
                .DEPTH(DQ),
                .ASYNC_RESET(ASYNC_RESET),
                .CANCEL_BITS(CANCEL_TIMEOUT_WIDTH)
            ) u_assertions (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_discard(discard ||!controls_known),
                .i_abort(active_cancel[c] || canceling),
                .i_start(start),
                .i_retire(retire[c]),
                .i_phase(phase[c]),
                .i_mode(owner.mode),
                .i_status(result_status[c]),
                .i_elements(owner.elements),
                .i_source_count(source_count),
                .i_destination_count(destination_count),
                .i_source_take(source_take),
                .i_sink_take(sink_take),
                .i_load_armed(load_armed[c]),
                .i_store_armed(store_armed[c]),
                .i_load_finished(load_finished[c]),
                .i_store_finished(store_finished[c]),
                .i_load_valid(o_load_config_valid[c]),
                .i_load_ready(i_load_config_ready[c]),
                .i_store_valid(o_store_config_valid[c]),
                .i_store_ready(i_store_config_ready[c]),
                .i_load_descriptor({
                    o_load_mode[c*2+:2],
                    o_load_base_address[c*W+:W],
                    o_load_element_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH],
                    o_load_inner_count[c*C+:C],
                    o_load_outer_count[c*C+:C],
                    o_load_inner_stride[c*W+:W],
                    o_load_outer_stride[c*W+:W],
                    o_load_space_id[c*S+:S],
                    o_load_context_id[c*X+:X],
                    o_load_channel_id[c*I+:I],
                    o_load_max_burst_beats[c*BURST_WIDTH+:BURST_WIDTH],
                    o_load_priority[c*P+:P],
                    o_load_descriptor_epoch[c*EP+:EP]
                }),
                .i_store_descriptor({
                    o_store_mode[c*2+:2],
                    o_store_base_address[c*W+:W],
                    o_store_element_size_log2[c*SIZE_WIDTH+:SIZE_WIDTH],
                    o_store_inner_count[c*C+:C],
                    o_store_outer_count[c*C+:C],
                    o_store_inner_stride[c*W+:W],
                    o_store_outer_stride[c*W+:W],
                    o_store_space_id[c*S+:S],
                    o_store_context_id[c*X+:X],
                    o_store_channel_id[c*I+:I],
                    o_store_max_burst_beats[c*BURST_WIDTH+:BURST_WIDTH],
                    o_store_priority[c*P+:P],
                    o_store_descriptor_epoch[c*EP+:EP]
                }),
                .i_store_data_valid(o_store_stream_valid[c]),
                .i_store_data_ready(i_store_stream_ready[c]),
                .i_tile_valid(o_stream_valid[c]),
                .i_tile_ready(i_stream_ready[c]),
                .i_store_data({
                    o_store_stream_data[c*D+:D],
                    o_store_stream_keep[c*DATA_BYTES+:DATA_BYTES],
                    o_store_stream_first[c],
                    o_store_stream_last[c],
                    o_store_stream_error[c]
                }),
                .i_tile_data({
                    o_stream_data[c*D+:D],
                    o_stream_keep[c*DATA_BYTES+:DATA_BYTES],
                    o_stream_first[c],
                    o_stream_descriptor_last[c],
                    o_stream_last[c],
                    o_stream_id[c*I+:I],
                    o_stream_context_id[c*X+:X],
                    o_stream_error[c]
                }),
                .i_fifo_push(data_push[c] && data_ready[c]),
                .i_fifo_pop(data_valid[c] && (data_pop[c] || discard || canceling)),
                .i_occupancy(o_data_fifo_occupancy[c*DATA_OCCUPANCY_WIDTH+:DATA_OCCUPANCY_WIDTH]),
                .i_cancel_timer(cancel_timer)
            );
`endif

            dff #(
                .WIDTH(COMMAND_BITS)
            ) u_active_descriptor (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(start),
                .i_d(queued_word),
                .o_q(active_packet[c])
            );
        end

        logic [4:0] pending_engine_error;
        logic pending_fatal;

        always_comb begin
            pending_engine_error = DMA_ERR_NONE;
            pending_fatal = ( | local_fatal) || completion_arb_error || event_arb_error;
            for (int c = N - 1; c >= 0; c -- )
            if (local_error[c] != DMA_ERR_NONE) pending_engine_error = local_error[c];
            if (command_accept && validation_error != DMA_ERR_NONE)
                pending_engine_error = validation_error;
            if (region_accept &&!region_legal) pending_engine_error = DMA_ERR_REGION;
            if (i_rstb !== 1'b1 ||!controls_known || unknown_command_channel ||
                unknown_cancel_channel || ( ^ i_event_pending === 1'bx))
                pending_engine_error = DMA_ERR_PROTOCOL;
            if (completion_arb_error || event_arb_error) pending_engine_error = DMA_ERR_OVERFLOW;
        end

        task automatic engine_update;
            if (!i_rstb) begin
                region_enabled <= '0;
                region_read <= '0;
                region_write <= '0;
                engine_error <= DMA_ERR_NONE;
                fatal_error <= 0;
                flushing <= 0;
                flush_seen <= 0;
                epoch <= '0;
                o_region_updated <= 0;
                o_region_rejected <= 0;
                o_command_accepted <= 0;
                o_command_rejected <= 0;
                o_cancel_accepted <= 0;
                o_cancel_not_found <= 0;
                o_flushed <= 0;
            end else begin
                o_region_updated <= 0;
                o_region_rejected <= 0;
                o_command_accepted <= 0;
                o_command_rejected <= 0;
                o_cancel_accepted <= 0;
                o_cancel_not_found <= 0;
                o_flushed <= 0;

                if (i_flush === 1'b0) flush_seen <= 0;
                if (flush_start) begin
                    flushing <= 1;
                    flush_seen <= 1;
                    epoch <= epoch + 1'b1;
                end

                if (flushing && all_queues_empty && all_channels_idle) begin
                    flushing <= 0;
                    o_flushed <= 1;
                end

                if (pending_fatal) fatal_error <= 1;
                // Clear acknowledges the old error; it must not erase a fault
                // arriving on this edge, particularly a newly fatal backend error.
                if (i_error_clear === 1'b1 && o_quiescent &&!fatal_error)
                    engine_error <= pending_engine_error;
                else if (engine_error == DMA_ERR_NONE && pending_engine_error != DMA_ERR_NONE)
                    engine_error <= pending_engine_error;
                if (region_accept) begin
                    o_region_updated <= region_legal;
                    o_region_rejected <=!region_legal;

                    if (region_legal) begin
                        region_enabled[i_region_index] <= i_region_enable;
                        region_read[i_region_index] <= i_region_read_enable;
                        region_write[i_region_index] <= i_region_write_enable;
                    end
                end

                if (command_accept) begin
                    o_command_accepted <= validation_error == DMA_ERR_NONE;
                    o_command_rejected <= validation_error != DMA_ERR_NONE;
                end

                if (cancel_accept) begin
                    o_cancel_accepted <= active_cancel[i_cancel_channel] ||
                        queue_cancel_match[i_cancel_channel];
                    o_cancel_not_found <=!(active_cancel[i_cancel_channel] ||
                        queue_cancel_match[i_cancel_channel]);
                end
            end
        endtask

        if (ASYNC_RESET == 1) begin : g_async
            always_ff @(posedge i_clk or negedge i_rstb) engine_update();
        end else begin : g_sync
            always_ff @(posedge i_clk) engine_update();
        end

        always_ff @(posedge i_clk)
            if (region_accept && region_legal) begin
                region_base[i_region_index] <= i_region_base;
                region_limit[i_region_index] <= i_region_limit;
                region_space[i_region_index] <= i_region_space_id;
                region_context[i_region_index] <= i_region_context_id;
            end
    end
endmodule
