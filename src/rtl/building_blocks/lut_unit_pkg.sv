`timescale 1ns / 1ps

// Repository-local contracts. Public command/round/protection values match the spec.
package lut_unit_pkg;
    typedef enum logic [1:0] {
        LUT_PROGRAM_WRITE = 2'd0,
        LUT_PROGRAM_READ = 2'd1,
        LUT_PROGRAM_COMMIT = 2'd2,
        LUT_PROGRAM_INVALIDATE = 2'd3
    } lut_command_t;

    typedef enum logic {
        LUT_ROUND_TO_ZERO = 1'b0,
        LUT_ROUND_NEAREST_EVEN = 1'b1
    } lut_round_t;

    typedef enum logic [1:0] {
        BUFFER_PROTECTION_NONE = 2'd0,
        BUFFER_PROTECTION_PARITY = 2'd1,
        BUFFER_PROTECTION_SECDED = 2'd2
    } lut_protection_t;

    typedef enum logic [3:0] {
        LUT_ERR_NONE,
        LUT_ERR_UNKNOWN,
        LUT_ERR_BANK,
        LUT_ERR_INVALID_BANK,
        LUT_ERR_INTERPOLATION,
        LUT_ERR_WRITE_COMMITTED,
        LUT_ERR_COVERAGE,
        LUT_ERR_BUSY,
        LUT_ERR_LIFECYCLE,
        LUT_ERR_CORRECTED,
        LUT_ERR_UNCORRECTABLE,
        LUT_ERR_INTERNAL
    } lut_error_t;
    localparam int ERROR_WIDTH = $bits(lut_error_t);
endpackage
