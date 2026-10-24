`timescale 1ns / 1ps
`default_nettype none

// Repository-local extension of the released scratchpad-bank error namespace.
// Bank values 0..9 translate identically; permission rejection is controller-local.
package scratchpad_controller_pkg;
    localparam int MEM_ERROR_WIDTH = 4;
    localparam int CTRL_ERROR_WIDTH = 4;

    typedef enum logic {
        MAP_LINEAR_STRIPED = 1'b0,
        MAP_XOR_STRIPED = 1'b1
    } mapping_mode_t;

    typedef enum logic [MEM_ERROR_WIDTH-1:0] {
        MEM_ERR_NONE = 4'd0,
        MEM_ERR_UNKNOWN_CONTROL = 4'd1,
        MEM_ERR_ADDRESS_RANGE = 4'd2,
        MEM_ERR_SIZE = 4'd3,
        MEM_ERR_ALIGNMENT = 4'd4,
        MEM_ERR_WORD_CROSSING = 4'd5,
        MEM_ERR_STROBE = 4'd6,
        MEM_ERR_PARITY = 4'd7,
        MEM_ERR_ECC_UNCORRECTABLE = 4'd8,
        MEM_ERR_INTERNAL_PROTOCOL = 4'd9,
        MEM_ERR_PERMISSION = 4'd10
    } memory_error_t;

    typedef enum logic [CTRL_ERROR_WIDTH-1:0] {
        CTRL_ERR_NONE = 4'd0,
        CTRL_ERR_UNKNOWN_TAG = 4'd1,
        CTRL_ERR_CLIENT = 4'd2,
        CTRL_ERR_SLOT = 4'd3,
        CTRL_ERR_UNALLOCATED = 4'd4,
        CTRL_ERR_DUPLICATE = 4'd5,
        CTRL_ERR_BANK = 4'd6,
        CTRL_ERR_OPERATION = 4'd7,
        CTRL_ERR_STATUS = 4'd8,
        CTRL_ERR_ARBITER = 4'd9
    } controller_error_t;

    // Per-client and per-bank groups in scratchpad_controller_counters.
    typedef enum int unsigned {
        CLIENT_COUNT_REQUESTS = 0,
        CLIENT_COUNT_RESPONSES = 1,
        CLIENT_COUNT_READ_BYTES = 2,
        CLIENT_COUNT_WRITE_BYTES = 3,
        CLIENT_COUNT_ARBITRATION_WAIT = 4,
        CLIENT_COUNT_FULL_STALL = 5,
        CLIENT_COUNT_RESPONSE_STALL = 6,
        CLIENT_COUNT_COLLECTOR_STALL = 7,
        CLIENT_COUNT_DENIED = 8,
        CLIENT_COUNT_UNKNOWN = 9,
        CLIENT_COUNT_RANGE = 10,
        CLIENT_COUNT_SIZE = 11,
        CLIENT_COUNT_ALIGNMENT = 12,
        CLIENT_COUNT_CROSSING = 13,
        CLIENT_COUNT_STROBE = 14
    } client_counter_index_t;

    typedef enum int unsigned {
        BANK_COUNT_READ_REQUESTS = 0,
        BANK_COUNT_WRITE_REQUESTS = 1,
        BANK_COUNT_READ_BYTES = 2,
        BANK_COUNT_WRITE_BYTES = 3,
        BANK_COUNT_CONTENTION = 4,
        BANK_COUNT_ARBITRATION_WAIT = 5,
        BANK_COUNT_NOT_READY = 6,
        BANK_COUNT_COLLECTOR_STALL = 7,
        BANK_COUNT_CORRECTED_RESPONSES = 8,
        BANK_COUNT_UNCORRECTABLE_RESPONSES = 9
    } controller_bank_counter_index_t;
endpackage
`default_nettype wire
