`timescale 1ns / 1ps
`default_nettype none

// Repository-local encodings. Parameter-dependent records remain in the body.
package vct_pkg;
    typedef enum logic [2:0] {
        VCT_LANE = 0,
        VCT_REDUCTION = 1,
        VCT_DOT = 2,
        VCT_BROADCAST = 3,
        VCT_EXTRACT = 4,
        VCT_PASS = 5
    } vct_fu_t;

    typedef enum logic [2:0] {
        VCT_ELEMENT_VECTOR = 0,
        VCT_PRODUCT_VECTOR = 1,
        VCT_ACC_VECTOR = 2,
        VCT_SCALAR_ELEMENT = 3,
        VCT_SCALAR_ACC = 4
    } vct_format_t;

    typedef enum logic [1:0] {
        VCT_PRED_ALWAYS = 0,
        VCT_PRED_EXTERNAL = 1,
        VCT_PRED_LOCAL = 2,
        VCT_PRED_NEVER = 3
    } vct_predicate_t;

    typedef enum logic [1:0] {
        VCT_ADVANCE_NONE = 0,
        VCT_ADVANCE_COUNT = 1,
        VCT_ADVANCE_PREDICATE = 2,
        VCT_ADVANCE_EVENT = 3
    } vct_advance_t;

    typedef enum logic [7:0] {
        VCT_ERR_CONTEXT = 8'h80,
        VCT_ERR_FORMAT = 8'h81,
        VCT_ERR_SOURCE = 8'h82,
        VCT_ERR_EMPTY = 8'h83,
        VCT_ERR_OVERFLOW = 8'h84,
        VCT_ERR_INTEGRITY = 8'h85,
        VCT_ERR_OWNERSHIP = 8'h86,
        VCT_ERR_CORRECTED = 8'h87
    } vct_error_t;
endpackage
`default_nettype wire
