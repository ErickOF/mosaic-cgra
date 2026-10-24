`timescale 1ns / 1ps

// Repository-local encodings. Parameter-dependent payloads remain in the RTL.
package rsqrt_unit_pkg;
    typedef enum logic {
        RSQRT_ARCH_ITERATIVE = 1'b0,
        RSQRT_ARCH_UNROLLED = 1'b1
    } rsqrt_arch_t;

    typedef enum logic {
        RSQRT_ROUND_TO_ZERO = 1'b0,
        RSQRT_ROUND_NEAREST_EVEN = 1'b1
    } rsqrt_round_t;

    typedef enum logic {
        RSQRT_ZERO_RETURN_ZERO = 1'b0,
        RSQRT_ZERO_SATURATE = 1'b1
    } rsqrt_zero_t;

    typedef enum logic [1:0] {
        SEED_PROTECTION_NONE = 2'd0,
        SEED_PROTECTION_PARITY = 2'd1,
        SEED_PROTECTION_SECDED = 2'd2
    } rsqrt_protection_t;

    typedef enum logic [3:0] {
        RSQRT_ERR_NONE = 4'd0,
        RSQRT_ERR_UNKNOWN = 4'd1,
        RSQRT_ERR_ITERATIONS = 4'd2,
        RSQRT_ERR_ZERO = 4'd3,
        RSQRT_ERR_CORRECTED = 4'd4,
        RSQRT_ERR_SEED = 4'd5,
        RSQRT_ERR_INTERNAL = 4'd6,
        RSQRT_ERR_OWNERSHIP = 4'd7,
        RSQRT_ERR_IMAGE = 4'd8,
        RSQRT_ERR_NEGATIVE = 4'd9,
        RSQRT_ERR_EPSILON = 4'd10
    } rsqrt_error_t;
endpackage
