`timescale 1ns / 1ps
`default_nettype none

// Repository-local baseline: datatype identifiers are opaque, known labels.
// Format-code order defines priority; the event bitmap retains all mismatches.
package stream_formatter_pkg;
    localparam int CONFIG_ERROR_WIDTH = 3;
    localparam int FORMAT_ERROR_WIDTH = 4;
    localparam int FORMAT_CLASSES = 11;

    typedef enum logic {
        FORMAT_GENERATE = 1'b0,
        FORMAT_VALIDATE = 1'b1
    } formatter_mode_t;

    typedef enum logic [CONFIG_ERROR_WIDTH-1:0] {
        CONFIG_ERR_NONE = 3'd0,
        CONFIG_ERR_UNKNOWN = 3'd1,
        CONFIG_ERR_FRAME_ZERO = 3'd2,
        CONFIG_ERR_ROW_ZERO = 3'd3,
        CONFIG_ERR_ROW_RANGE = 3'd4,
        CONFIG_ERR_LANES_EMPTY = 3'd5
    } config_error_t;

    typedef enum logic [FORMAT_ERROR_WIDTH-1:0] {
        FORMAT_ERR_NONE = 4'd0,
        FORMAT_ERR_UNKNOWN_CONTROL = 4'd1,
        FORMAT_ERR_EMPTY_BEAT = 4'd2,
        FORMAT_ERR_LANE_KEEP = 4'd3,
        FORMAT_ERR_FIRST = 4'd4,
        FORMAT_ERR_LAST = 4'd5,
        FORMAT_ERR_ROW_FIRST = 4'd6,
        FORMAT_ERR_ROW_LAST = 4'd7,
        FORMAT_ERR_END_OF_STREAM = 4'd8,
        FORMAT_ERR_DATATYPE = 4'd9,
        FORMAT_ERR_CHANNEL = 4'd10,
        FORMAT_ERR_CONTEXT = 4'd11
    } format_error_t;
endpackage
`default_nettype wire
