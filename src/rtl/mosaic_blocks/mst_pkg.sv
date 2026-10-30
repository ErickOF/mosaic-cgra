`timescale 1ns / 1ps
// Repository-local v1 MST encodings. Parameter-dependent records stay local.
package mst_pkg;
    typedef enum logic [2:0] {
        MST_LOAD_STREAM = 0,
        MST_STORE_STREAM = 1,
        MST_LOCAL_COPY = 2,
        MST_DMA_TO_STREAM = 3,
        MST_STREAM_TO_DMA = 4,
        MST_DMA_TO_MEMORY = 5,
        MST_MEMORY_TO_DMA = 6,
        MST_STREAM_FORWARD = 7
    } transfer_t;

    typedef enum logic [2:0] {
        MST_ADDR_LINEAR = 0,
        MST_ADDR_STRIDED_1D = 1,
        MST_ADDR_STRIDED_2D = 2,
        MST_ADDR_STRIDED_3D = 3,
        MST_ADDR_CIRCULAR = 4,
        MST_ADDR_INDEXED = 5
    } address_t;

    typedef enum logic [2:0] {
        MST_SPACE_SCRATCHPAD = 0,
        MST_SPACE_LOCAL_BUFFER = 1,
        MST_SPACE_TILE_STREAM = 2,
        MST_SPACE_DMA_STREAM = 3,
        MST_SPACE_GLOBAL_STREAM = 4,
        MST_SPACE_MEMORY_PROXY = 5
    } space_t;

    typedef enum logic [2:0] {
        BUFFER_FREE = 0,
        BUFFER_FILLING = 1,
        BUFFER_FULL = 2,
        BUFFER_CONSUMING = 3,
        BUFFER_DRAINING = 4,
        BUFFER_ERROR = 5
    } buffer_state_t;

    typedef enum logic [1:0] {
        MST_SUCCESS = 0,
        MST_FAILED = 1,
        MST_CANCELED = 2,
        MST_CONTAINED = 3
    } completion_status_t;

    typedef enum logic [3:0] {
        MST_CMD_FREE = 0,
        MST_CMD_QUEUED = 1,
        MST_CMD_WAIT_EVENT = 2,
        MST_CMD_VALIDATING = 3,
        MST_CMD_RESERVING = 4,
        MST_CMD_ACTIVE = 5,
        MST_CMD_DRAINING = 6,
        MST_CMD_COMPLETING = 7,
        MST_CMD_SUSPENDED = 8,
        MST_CMD_CANCELING = 9,
        MST_CMD_ERROR = 10
    } command_state_t;

    typedef enum logic [7:0] {
        MST_OK = 0,
        MST_ERR_UNKNOWN = 1,
        MST_ERR_IDENTITY = 2,
        MST_ERR_MODE = 3,
        MST_ERR_CHANNEL = 4,
        MST_ERR_COUNT = 5,
        MST_ERR_SIZE = 6,
        MST_ERR_ALIGNMENT = 7,
        MST_ERR_BOUNDS = 8,
        MST_ERR_REGION = 9,
        MST_ERR_PERMISSION = 10,
        MST_ERR_BUFFER = 11,
        MST_ERR_GENERATION = 12,
        MST_ERR_OVERLAP = 13,
        MST_ERR_FORMAT = 14,
        MST_ERR_EVENT = 15,
        MST_ERR_DUPLICATE = 16,
        MST_ERR_MEMORY = 17,
        MST_ERR_TAG = 18,
        MST_ERR_TIMEOUT = 19,
        MST_ERR_CANCELED = 20,
        MST_ERR_DEPENDENCY = 21,
        MST_ERR_INTEGRITY = 22,
        MST_ERR_CONTAINMENT = 23,
        MST_ERR_CONTEXT = 24,
        MST_ERR_RESOURCE = 25
    } error_t;

    typedef struct packed {
        logic valid;
        logic error;
        logic [7:0] code;
    } management_response_t;

    function automatic logic memory_source(input logic [2:0] mode);
        return mode == MST_LOAD_STREAM || mode == MST_LOCAL_COPY || mode == MST_MEMORY_TO_DMA;
    endfunction

    function automatic logic memory_destination(input logic [2:0] mode);
        return mode == MST_STORE_STREAM || mode == MST_LOCAL_COPY || mode == MST_DMA_TO_MEMORY;
    endfunction

    function automatic logic load_class(input logic [2:0] mode);
        return memory_source(mode) || mode == MST_DMA_TO_STREAM;
    endfunction
endpackage
