`timescale 1ns / 1ps
`default_nettype none

// Repository-local contracts, following the existing AGU/load error inventory.
// Stream fault priority follows the store specification, independently of codes.
package store_engine_pkg;
    localparam int ERROR_CODE_WIDTH = 5;
    typedef enum logic [ERROR_CODE_WIDTH-1:0] {
        STORE_ERR_NONE = 5'd0,
        STORE_ERR_MODE = 5'd1,
        STORE_ERR_INNER_COUNT = 5'd2,
        STORE_ERR_OUTER_COUNT = 5'd3,
        STORE_ERR_1D_OUTER_COUNT = 5'd4,
        STORE_ERR_ELEMENT_SIZE = 5'd5,
        STORE_ERR_BASE_ALIGNMENT = 5'd6,
        STORE_ERR_INNER_ALIGNMENT = 5'd7,
        STORE_ERR_OUTER_ALIGNMENT = 5'd8,
        STORE_ERR_DESCRIPTOR_UNKNOWN = 5'd9,
        STORE_ERR_ADDRESS_RANGE = 5'd10,
        STORE_ERR_AGU = 5'd11,
        STORE_ERR_TAG_RANGE = 5'd12,
        STORE_ERR_TAG_UNALLOCATED = 5'd13,
        STORE_ERR_TAG_DUPLICATE = 5'd14,
        STORE_ERR_RESPONSE_UNKNOWN = 5'd15,
        STORE_ERR_STREAM_UNKNOWN = 5'd16,
        STORE_ERR_STREAM_UPSTREAM = 5'd17,
        STORE_ERR_STREAM_CONTEXT = 5'd18,
        STORE_ERR_STREAM_CHANNEL = 5'd19,
        STORE_ERR_STREAM_KEEP = 5'd20,
        STORE_ERR_STREAM_FRAMING = 5'd21
    } store_error_t;

    typedef enum int unsigned {
        STORE_COUNT_COMMANDS_STARTED = 0,
        STORE_COUNT_COMMANDS_COMPLETED = 1,
        STORE_COUNT_COMMANDS_FAILED = 2,
        STORE_COUNT_STREAM_BEATS = 3,
        STORE_COUNT_STREAM_BYTES = 4,
        STORE_COUNT_REQUESTS = 5,
        STORE_COUNT_RESPONSES = 6,
        STORE_COUNT_RESPONSES_RETIRED = 7,
        STORE_COUNT_STARVATION = 8,
        STORE_COUNT_REQUEST_STALLS = 9,
        STORE_COUNT_OLDEST_WAITS = 10,
        STORE_COUNT_FULL_CYCLES = 11,
        STORE_COUNT_MEMORY_ERRORS = 12,
        STORE_COUNT_STREAM_UNKNOWN = 13,
        STORE_COUNT_STREAM_UPSTREAM = 14,
        STORE_COUNT_STREAM_CONTEXT = 15,
        STORE_COUNT_STREAM_CHANNEL = 16,
        STORE_COUNT_STREAM_KEEP = 17,
        STORE_COUNT_STREAM_FRAMING = 18,
        STORE_COUNT_RESPONSE_PROTOCOL = 19
    } store_counter_index_t;
endpackage
`default_nettype wire
