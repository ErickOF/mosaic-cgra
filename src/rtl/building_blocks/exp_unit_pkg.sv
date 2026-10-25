`timescale 1ns / 1ps

// Repository-local baseline encodings, consistent with other MOSAIC packages.
package exp_unit_pkg;
    typedef enum logic {
        EXP_BASE_E = 1'b0,
        EXP_BASE_2 = 1'b1
    } exp_base_t;

    typedef enum logic {
        EXP_ROUND_TO_ZERO = 1'b0,
        EXP_ROUND_NEAREST_EVEN = 1'b1
    } exp_round_t;

    typedef enum logic [1:0] {
        TABLE_PROTECTION_NONE = 2'd0,
        TABLE_PROTECTION_PARITY = 2'd1,
        TABLE_PROTECTION_SECDED = 2'd2
    } exp_protection_t;

    typedef enum logic [3:0] {
        EXP_ERR_NONE = 4'd0,
        EXP_ERR_BASE = 4'd1,
        EXP_ERR_INTERPOLATION = 4'd2,
        EXP_ERR_UNKNOWN = 4'd3,
        EXP_ERR_CORRECTED = 4'd4,
        EXP_ERR_TABLE = 4'd5,
        EXP_ERR_RANGE = 4'd6,
        EXP_ERR_IDENTITY = 4'd7,
        EXP_ERR_OWNERSHIP = 4'd8,
        EXP_ERR_ARITHMETIC = 4'd9
    } exp_error_t;
endpackage
