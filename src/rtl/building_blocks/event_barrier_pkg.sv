`timescale 1ns / 1ps

// Repository-local baseline encodings, following the other MOSAIC RTL packages.
package event_barrier_pkg;
    typedef enum logic [1:0] {
        EVENT_WAIT_ANY = 2'd0,
        EVENT_WAIT_ALL = 2'd1
    } event_wait_mode_t;

    typedef enum logic [1:0] {
        EVENT_ACK_ONE = 2'd0,
        EVENT_CLEAR_ALL = 2'd1
    } event_ack_mode_t;

    typedef enum logic {
        EVENT_WAIT_SATISFIED = 1'b0,
        EVENT_WAIT_CANCELED = 1'b1
    } event_wait_status_t;

    typedef enum logic [3:0] {
        EB_ERR_NONE = 4'd0,
        EB_ERR_POLICY = 4'd1,
        EB_ERR_POST = 4'd2,
        EB_ERR_ACK = 4'd3,
        EB_ERR_WAIT = 4'd4,
        EB_ERR_CANCEL = 4'd5,
        EB_ERR_BARRIER_CONFIG = 4'd6,
        EB_ERR_ARRIVAL = 4'd7,
        EB_ERR_DUPLICATE = 4'd8,
        EB_ERR_STALE = 4'd9,
        EB_ERR_UNKNOWN = 4'd10,
        EB_ERR_STATE = 4'd11
    } event_barrier_error_t;
endpackage
