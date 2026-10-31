`timescale 1ns / 1ps
package predicate_network_pkg;
    // Repository-local v1 encodings. No external contracts package is assumed.
    typedef enum logic [2:0] {
        PRED_PHASE_READY = 0,
        PRED_PHASE_CHECK = 1,
        PRED_PHASE_DEPTH = 2,
        PRED_PHASE_INSTALL = 3,
        PRED_PHASE_ACK = 4
    } phase_t;

    typedef enum logic [1:0] {
        PRED_CLASS_SCALAR = 0,
        PRED_CLASS_VECTOR = 1,
        PRED_CLASS_EMPTY_SCALAR = 2,
        PRED_CLASS_EMPTY_VECTOR = 3
    } predicate_class_t;

    typedef enum logic [7:0] {
        PRED_NET_OK = 0,
        PRED_NET_ERR_UNKNOWN = 1,
        PRED_NET_ERR_ROUTE = 2,
        PRED_NET_ERR_FANOUT = 3,
        PRED_NET_ERR_TREE = 4,
        PRED_NET_ERR_DEPENDENCY = 5,
        PRED_NET_ERR_VERSION = 6,
        PRED_NET_ERR_PROOF = 7,
        PRED_NET_ERR_SCHEDULE = 8,
        PRED_NET_ERR_FAULT = 9,
        PRED_NET_ERR_LANE = 10,
        PRED_NET_ERR_CONTEXT = 11,
        PRED_NET_ERR_EPOCH = 12,
        PRED_NET_ERR_PRODUCER = 13,
        PRED_NET_ERR_ALIGNMENT = 14,
        PRED_NET_ERR_PARITY = 15,
        PRED_NET_ERR_INTEGRITY = 16,
        PRED_NET_ERR_COUNTER = 17
    } error_t;
endpackage
