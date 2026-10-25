`timescale 1ns / 1ps
`default_nettype none

// Local encodings shared by the controller and its tile wrapper.
package tile_power_controller_pkg;
    localparam int POWER_STATE_WIDTH = 4;
    localparam int POWER_COMMAND_WIDTH = 3;
    localparam int POWER_ERROR_WIDTH = 4;
    localparam int POWER_RESIDENCY_WIDTH = 32;

    typedef enum logic [POWER_STATE_WIDTH-1:0] {
        PWR_RESET = 4'd0,
        PWR_ACTIVE = 4'd1,
        PWR_STALLED = 4'd2,
        PWR_IDLE = 4'd3,
        PWR_DRAINING = 4'd4,
        PWR_SAVING = 4'd5,
        PWR_ISOLATING = 4'd6,
        PWR_POWERING_DOWN = 4'd7,
        PWR_RETENTION = 4'd8,
        PWR_OFF = 4'd9,
        PWR_POWERING_UP = 4'd10,
        PWR_RESTORING = 4'd11,
        PWR_REINITIALIZING = 4'd12,
        PWR_WAKEUP = 4'd13,
        PWR_ERROR = 4'd14
    } power_state_t;

    typedef enum logic [POWER_COMMAND_WIDTH-1:0] {
        POWER_RUN = 3'd0,
        POWER_IDLE = 3'd1,
        POWER_RETENTION = 3'd2,
        POWER_OFF = 3'd3
    } power_command_t;

    typedef enum logic [POWER_ERROR_WIDTH-1:0] {
        PWR_ERR_NONE = 4'd0,
        PWR_ERR_COMMAND = 4'd1,
        PWR_ERR_CONTEXT = 4'd2,
        PWR_ERR_TRANSITION = 4'd3,
        PWR_ERR_UNKNOWN = 4'd4,
        PWR_ERR_DRAIN_TIMEOUT = 4'd5,
        PWR_ERR_SAVE_TIMEOUT = 4'd6,
        PWR_ERR_RESTORE_TIMEOUT = 4'd7,
        PWR_ERR_ACK = 4'd8,
        PWR_ERR_POWER_UP_TIMEOUT = 4'd9,
        PWR_ERR_POWER_DOWN_TIMEOUT = 4'd10,
        PWR_ERR_POWER_LOSS = 4'd11,
        PWR_ERR_TEST = 4'd12,
        PWR_ERR_CONFIG = 4'd13,
        PWR_ERR_SEQUENCE = 4'd14
    } power_error_t;

    function automatic logic stable_state(input logic [POWER_STATE_WIDTH-1:0] state);
        case (state)
            PWR_ACTIVE, PWR_STALLED, PWR_IDLE, PWR_RETENTION, PWR_OFF, PWR_ERROR:
                return 1'b1;
            default: return 1'b0;
        endcase
    endfunction
endpackage
`default_nettype wire
