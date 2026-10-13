`timescale 1ns / 1ps

// Repository-local interface version. No external contracts package is required.
// Keep encodings shared by every sequencer and integration fixture in this repo.
package context_sequencer_pkg;
    localparam int unsigned INTERFACE_VERSION = 1;
    typedef enum logic [2:0] {
        CONTEXT_HOLD = 3'd0,
        CONTEXT_INCREMENT = 3'd1,
        CONTEXT_JUMP = 3'd2,
        CONTEXT_LOOP = 3'd3,
        CONTEXT_END = 3'd4
    } context_transition_mode_t;

    typedef enum logic [2:0] {
        SEQ_ERR_NONE = 3'd0,
        SEQ_ERR_ACTIVE_INVALID = 3'd1,
        SEQ_ERR_ADDRESS = 3'd2,
        SEQ_ERR_TRANSITION = 3'd3,
        SEQ_ERR_LOOP = 3'd4,
        SEQ_ERR_COMMAND = 3'd5,
        SEQ_ERR_PROTOCOL = 3'd6
    } sequencer_error_code_t;

    localparam int unsigned TRANSITION_MODE_WIDTH = $bits(context_transition_mode_t);
    localparam int unsigned ERROR_CODE_WIDTH = $bits(sequencer_error_code_t);
endpackage
