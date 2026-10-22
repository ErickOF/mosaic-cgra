`timescale 1ns / 1ps

// Repository-local encodings. Modes retain agu_pkg's baseline encodings.
package load_engine_pkg;
    localparam int ERROR_CODE_WIDTH = 4;
    typedef enum logic [ERROR_CODE_WIDTH-1:0] {
        LOAD_ERR_NONE = 4'd0,
        LOAD_ERR_MODE = 4'd1,
        LOAD_ERR_INNER_COUNT = 4'd2,
        LOAD_ERR_OUTER_COUNT = 4'd3,
        LOAD_ERR_1D_OUTER_COUNT = 4'd4,
        LOAD_ERR_ELEMENT_SIZE = 4'd5,
        LOAD_ERR_BASE_ALIGNMENT = 4'd6,
        LOAD_ERR_INNER_ALIGNMENT = 4'd7,
        LOAD_ERR_OUTER_ALIGNMENT = 4'd8,
        LOAD_ERR_DESCRIPTOR_UNKNOWN = 4'd9,
        LOAD_ERR_ADDRESS_RANGE = 4'd10,
        LOAD_ERR_AGU = 4'd11,
        LOAD_ERR_TAG_RANGE = 4'd12,
        LOAD_ERR_TAG_UNALLOCATED = 4'd13,
        LOAD_ERR_TAG_DUPLICATE = 4'd14,
        LOAD_ERR_RESPONSE_UNKNOWN = 4'd15
    } load_error_t;

    typedef enum int unsigned {
        LOAD_COUNT_COMMANDS_STARTED = 0,
        LOAD_COUNT_COMMANDS_COMPLETED = 1,
        LOAD_COUNT_COMMANDS_FAILED = 2,
        LOAD_COUNT_REQUESTS = 3,
        LOAD_COUNT_RESPONSES = 4,
        LOAD_COUNT_STREAM_BEATS = 5,
        LOAD_COUNT_REQUEST_STALLS = 6,
        LOAD_COUNT_OLDEST_WAITS = 7,
        LOAD_COUNT_STREAM_STALLS = 8,
        LOAD_COUNT_FULL_CYCLES = 9,
        LOAD_COUNT_MEMORY_ERRORS = 10,
        LOAD_COUNT_PROTOCOL_ERRORS = 11,
        LOAD_COUNT_STREAM_BYTES = 12
    } load_counter_index_t;
endpackage
