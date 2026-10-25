`timescale 1ns / 1ps

// Repository-local encodings shared by the unit and integration clients.
package reciprocal_unit_pkg;
    typedef enum logic {
        RECIP_ARCH_ITERATIVE = 1'b0,
        RECIP_ARCH_UNROLLED = 1'b1
    } reciprocal_arch_t;

    typedef enum logic {
        RECIP_ROUND_TO_ZERO = 1'b0,
        RECIP_ROUND_NEAREST_EVEN = 1'b1
    } reciprocal_round_t;

    typedef enum logic {
        RECIP_ZERO_RETURN_ZERO = 1'b0,
        RECIP_ZERO_SATURATE = 1'b1
    } reciprocal_zero_t;

    typedef enum logic [1:0] {
        SEED_PROTECTION_NONE = 2'd0,
        SEED_PROTECTION_PARITY = 2'd1,
        SEED_PROTECTION_SECDED = 2'd2
    } reciprocal_protection_t;

    typedef enum logic [3:0] {
        RECIP_ERR_NONE = 4'd0,
        RECIP_ERR_UNKNOWN = 4'd1,
        RECIP_ERR_ITERATIONS = 4'd2,
        RECIP_ERR_ZERO = 4'd3,
        RECIP_ERR_CORRECTED = 4'd4,
        RECIP_ERR_SEED = 4'd5,
        RECIP_ERR_INTERNAL = 4'd6,
        RECIP_ERR_OWNERSHIP = 4'd7,
        RECIP_ERR_IMAGE = 4'd8
    } reciprocal_error_t;
endpackage
