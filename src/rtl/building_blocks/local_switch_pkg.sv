`timescale 1ns / 1ps

// Repository-local static-route errors. Payload and context bits stay opaque.
package local_switch_pkg;
    localparam int ERROR_CODE_WIDTH = 3;
    typedef enum logic [ERROR_CODE_WIDTH-1:0] {
        SWITCH_ERR_NONE = 3'd0,
        SWITCH_ERR_SOURCE = 3'd1,
        SWITCH_ERR_CONNECTIVITY = 3'd2,
        SWITCH_ERR_MULTICAST = 3'd3,
        SWITCH_ERR_UNKNOWN = 3'd4,
        SWITCH_ERR_EMPTY_PENDING = 3'd5,
        SWITCH_ERR_PENDING_ROUTE = 3'd6,
        SWITCH_ERR_BUFFER_STATE = 3'd7
    } switch_error_t;
endpackage
