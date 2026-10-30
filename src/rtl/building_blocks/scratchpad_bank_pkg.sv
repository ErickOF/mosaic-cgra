`timescale 1ns / 1ps
`default_nettype none

// Repository-local memory encodings; physical layouts follow parity/ecc helpers.
package scratchpad_bank_pkg;
    localparam int BANK_ERROR_WIDTH = 4;
    typedef enum logic [1:0] {
        PROTECT_NONE = 2'd0,
        PROTECT_PARITY = 2'd1,
        PROTECT_SECDED = 2'd2
    } protection_mode_t;

    typedef enum logic [BANK_ERROR_WIDTH-1:0] {
        BANK_ERR_NONE = 4'd0,
        BANK_ERR_UNKNOWN_CONTROL = 4'd1,
        BANK_ERR_ADDRESS_RANGE = 4'd2,
        BANK_ERR_SIZE = 4'd3,
        BANK_ERR_ALIGNMENT = 4'd4,
        BANK_ERR_WORD_CROSSING = 4'd5,
        BANK_ERR_STROBE = 4'd6,
        BANK_ERR_PARITY = 4'd7,
        BANK_ERR_ECC_UNCORRECTABLE = 4'd8,
        BANK_ERR_INTERNAL_PROTOCOL = 4'd9
    } bank_error_t;

    typedef enum logic [1:0] {
        BANK_WORK_IDLE = 2'd0,
        BANK_WORK_WAIT = 2'd1,
        BANK_WORK_COMMIT = 2'd2
    } bank_work_state_t;

    typedef enum int unsigned {
        BANK_COUNT_READS = 0,
        BANK_COUNT_WRITES = 1,
        BANK_COUNT_READ_BYTES = 2,
        BANK_COUNT_WRITE_BYTES = 3,
        BANK_COUNT_READ_RESPONSES = 4,
        BANK_COUNT_WRITE_RESPONSES = 5,
        BANK_COUNT_REQUEST_STALLS = 6,
        BANK_COUNT_RESPONSE_STALLS = 7,
        BANK_COUNT_FULL = 8,
        BANK_COUNT_PARTIAL_WRITES = 9,
        BANK_COUNT_RMW = 10,
        BANK_COUNT_WORK_STALLS = 11,
        BANK_COUNT_CORRECTED = 12,
        BANK_COUNT_SCRUBS = 13,
        BANK_COUNT_PARITY_ERRORS = 14,
        BANK_COUNT_ECC_ERRORS = 15,
        BANK_COUNT_UNKNOWN = 16,
        BANK_COUNT_ADDRESS_RANGE = 17,
        BANK_COUNT_SIZE = 18,
        BANK_COUNT_ALIGNMENT = 19,
        BANK_COUNT_WORD_CROSSING = 20,
        BANK_COUNT_STROBE = 21,
        BANK_COUNT_FLUSHES = 22
    } bank_counter_index_t;
endpackage
`default_nettype wire
