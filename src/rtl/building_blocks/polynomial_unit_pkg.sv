`timescale 1ns / 1ps

// Repository-local encodings; platform integration maps any external contracts.
package polynomial_unit_pkg;
    typedef enum logic {
        POLY_ARCH_ITERATIVE = 1'b0,
        POLY_ARCH_UNROLLED = 1'b1
    } polynomial_arch_t;

    typedef enum logic [1:0] {
        POLY_PROGRAM_WRITE = 2'd0,
        POLY_PROGRAM_READ = 2'd1,
        POLY_PROGRAM_COMMIT = 2'd2,
        POLY_PROGRAM_INVALIDATE = 2'd3
    } polynomial_command_t;

    typedef enum logic {
        POLY_RANGE_CLIP = 1'b0,
        POLY_RANGE_ERROR = 1'b1
    } polynomial_range_t;

    typedef enum logic {
        POLY_ROUND_TO_ZERO = 1'b0,
        POLY_ROUND_NEAREST_EVEN = 1'b1
    } polynomial_round_t;

    typedef enum logic [4:0] {
        POLY_ERR_NONE,
        POLY_ERR_UNKNOWN,
        POLY_ERR_BANK,
        POLY_ERR_UNCOMMITTED,
        POLY_ERR_COMMITTED,
        POLY_ERR_INDEX,
        POLY_ERR_DEGREE,
        POLY_ERR_DOMAIN,
        POLY_ERR_SHIFT,
        POLY_ERR_INCOMPLETE,
        POLY_ERR_BUSY,
        POLY_ERR_RANGE,
        POLY_ERR_COEFFICIENT,
        POLY_ERR_CORRECTED,
        POLY_ERR_INTERNAL
    } polynomial_error_t;

    localparam int ERROR_WIDTH = $bits(polynomial_error_t);
endpackage
