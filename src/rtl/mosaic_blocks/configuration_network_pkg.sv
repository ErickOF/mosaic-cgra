`timescale 1ns / 1ps
package configuration_network_pkg;
    // Repository-local v1. Endpoint IDs are architectural; tree indices are not.
    typedef enum logic [3:0] {
        CFG_NOP = 0,
        CFG_WRITE = 1,
        CFG_READ = 2,
        CFG_VALIDATE = 3,
        CFG_INVALIDATE = 4,
        CFG_QUERY = 5,
        CFG_PREPARE = 6,
        CFG_ABORT_PREPARE = 7,
        CFG_COMMIT = 8,
        CFG_DRAIN = 9,
        CFG_FLUSH = 10
    } command_t;
    typedef enum logic [3:0] {
        CFG_SUCCESS = 0,
        CFG_REJECTED = 1,
        CFG_TIMEOUT = 2,
        CFG_CANCELED = 3,
        CFG_NOT_PRESENT = 4
    } status_t;
    typedef enum logic [7:0] {
        CFG_OK = 0,
        CFG_ERR_UNKNOWN = 1,
        CFG_ERR_COMMAND = 2,
        CFG_ERR_DESTINATION = 3,
        CFG_ERR_CAPABILITY = 4,
        CFG_ERR_PERMISSION = 5,
        CFG_ERR_SCHEMA = 6,
        CFG_ERR_WORD = 7,
        CFG_ERR_CONTEXT = 8,
        CFG_ERR_VERSION = 9,
        CFG_ERR_EPOCH = 10,
        CFG_ERR_CRC = 11,
        CFG_ERR_FRAME = 12,
        CFG_ERR_IDENTITY = 13,
        CFG_ERR_ENDPOINT = 14,
        CFG_ERR_TIMEOUT = 15,
        CFG_ERR_RESPONSE = 16,
        CFG_ERR_PREPARE = 17,
        CFG_ERR_COMMIT = 18,
        CFG_ERR_POWER = 19,
        CFG_ERR_INTEGRITY = 20,
        CFG_ERR_CANCELED = 21,
        CFG_ERR_OVERFLOW = 22,
        CFG_ERR_IMAGE_CRC = 23,
        CFG_ERR_PACKAGE = 24
    } error_t;
    typedef enum logic [2:0] {
        ADAPTER_IDLE = 0,
        ADAPTER_QUERY_SEND = 1,
        ADAPTER_QUERY_WAIT = 2,
        ADAPTER_NATIVE_SEND = 3,
        ADAPTER_NATIVE_WAIT = 4,
        ADAPTER_COMMIT_WAIT = 5,
        ADAPTER_PREPARE_CHECK = 6
    } adapter_phase_t;
    typedef enum logic [2:0] {
        COMMIT_IDLE = 0,
        COMMIT_HOLD = 1,
        COMMIT_DELIVER = 2,
        COMMIT_ACK = 3,
        COMMIT_HELD = 4,
        COMMIT_FAILED = 5
    } commit_phase_t;
endpackage
