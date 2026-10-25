`timescale 1ns / 1ps

// Repository-local baseline encodings. Integration with an external memory
// contract must map these enums explicitly; identifiers remain opaque metadata.
package agu_pkg;
    typedef enum logic [1:0] {
        AGU_LINEAR_1D = 2'b00,
        AGU_STRIDED_1D = 2'b01,
        AGU_STRIDED_2D = 2'b10
    } agu_mode_t;

    localparam int ERROR_CODE_WIDTH = 4;
    typedef enum logic [ERROR_CODE_WIDTH-1:0] {
        AGU_ERR_NONE = 4'd0,
        AGU_ERR_MODE = 4'd1,
        AGU_ERR_INNER_COUNT = 4'd2,
        AGU_ERR_OUTER_COUNT = 4'd3,
        AGU_ERR_1D_OUTER_COUNT = 4'd4,
        AGU_ERR_ELEMENT_SIZE = 4'd5,
        AGU_ERR_BASE_ALIGNMENT = 4'd6,
        AGU_ERR_INNER_ALIGNMENT = 4'd7,
        AGU_ERR_OUTER_ALIGNMENT = 4'd8,
        AGU_ERR_UNKNOWN_FIELD = 4'd9,
        AGU_ERR_UNDERFLOW = 4'd10,
        AGU_ERR_OVERFLOW = 4'd11
    } agu_error_t;
endpackage
