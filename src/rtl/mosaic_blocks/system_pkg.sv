`timescale 1ns / 1ps
`default_nettype none
// Repository-local System-RTL ABI. Generated headers describe external byte order.
package system_pkg;
    typedef enum logic [7:0] {
        SYS_RUNTIME = 0,
        SYS_CONFIG = 1,
        SYS_PACKAGE = 2,
        SYS_REGION = 3,
        SYS_BUFFER = 4,
        SYS_DESCRIPTOR = 5,
        SYS_NOC = 6,
        SYS_LOAD = 7,
        SYS_STORE = 8,
        SYS_WAIT = 9,
        SYS_FENCE = 10,
        SYS_SRAM = 11,
        SYS_SESSION_END = 12
    } system_record_kind_t;

    typedef enum logic [7:0] {
        SYS_OK = 0,
        SYS_DECODE = 1,
        SYS_PERMISSION = 2,
        SYS_ALIGNMENT = 3,
        SYS_STROBE = 4,
        SYS_BUSY = 5,
        SYS_DESCRIPTOR_ERROR = 6,
        SYS_GENERATION = 7,
        SYS_BOUNDS = 8,
        SYS_OWNERSHIP = 9,
        SYS_MEMORY = 10,
        SYS_TIMEOUT = 11,
        SYS_ARRAY = 12,
        SYS_CANCELED = 13,
        SYS_INTEGRITY = 14,
        SYS_UNSUPPORTED = 15
    } system_error_t;

    typedef enum logic [1:0] {
        SYS_HOST_OWNED = 0,
        SYS_DMA_OWNED = 1,
        SYS_TRANSFER = 2,
        SYS_INVALID = 3
    } system_buffer_state_t;

    typedef enum logic [4:0] {
        SYS_IDLE,
        SYS_FETCH_REQUEST,
        SYS_FETCH_READ,
        SYS_CHECK,
        SYS_ISSUE,
        SYS_REPLY,
        SYS_NEXT,
        SYS_FINISH,
        SYS_COPY_CHECK,
        SYS_COPY_READ_REQUEST,
        SYS_COPY_READ,
        SYS_COPY_LOCAL_ISSUE,
        SYS_COPY_LOCAL_REPLY,
        SYS_COPY_WRITE_REQUEST,
        SYS_COPY_WRITE_DATA,
        SYS_COPY_WRITE_REPLY,
        SYS_COPY_NEXT,
        SYS_WAIT_ARRAY,
        SYS_FENCE_REQUEST,
        SYS_FENCE_REPLY
    } system_phase_t;

    typedef struct packed {
        logic [31:0] timestamp;
        logic [15:0] detail;
        logic [15:0] tag;
        logic [31:0] source_sequence;
        logic [255:0] payload;
        logic [31:0] sequence_id;
        logic [15:0] generation;
        logic [7:0] context_id;
        logic [7:0] epoch;
        logic [31:0] package_id;
        logic [15:0] kernel;
        logic [15:0] owner;
        logic [15:0] source;
        logic [5:0] flags;
        logic [1:0] severity;
        logic [7:0] kind;
    } system_event_t;

    // One immutable register-resident region; the program itself lives in memory.
    typedef struct packed {
        logic valid;
        logic [63:0] base;
        logic [31:0] size;
        logic [15:0] owner;
        logic [15:0] kernel;
        logic [15:0] generation;
        logic [1:0] permissions;
    } system_region_t;

    function automatic logic [31:0] system_crc(input logic [2047:0] record_data);
        logic [31:0] crc;
        logic bit_value;
        crc = 32'hffffffff;

        for (int bit_index = 0; bit_index < 2048; bit_index++) begin
            bit_value = bit_index >= 224 && bit_index < 256 ?
                1'b0 : record_data[bit_index];
            crc = crc_pkg::crc32c_step(crc, crc[0] ^ bit_value);
        end

        return ~crc;
    endfunction
endpackage
`default_nettype wire
