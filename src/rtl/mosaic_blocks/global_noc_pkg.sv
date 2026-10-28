`timescale 1ns / 1ps
package global_noc_pkg;
    typedef enum logic [2:0] {
        NOC_DATA = 0,
        NOC_REDUCTION = 1,
        NOC_REQUEST = 2,
        NOC_RESPONSE = 3,
        NOC_EVENT = 4,
        NOC_RUNTIME = 5,
        NOC_MIGRATION = 6,
        NOC_DEBUG = 7
    } traffic_class_t;

    typedef enum logic [2:0] {
        NOC_CFG_WRITE = 0,
        NOC_CFG_READ = 1,
        NOC_CFG_VALIDATE = 2,
        NOC_CFG_PREPARE = 3,
        NOC_CFG_COMMIT = 4,
        NOC_CFG_ABORT = 5,
        NOC_CFG_STATUS = 6
    } config_command_t;

    typedef enum logic [3:0] {
        NOC_CFG_OK = 0,
        NOC_CFG_COMMAND = 1,
        NOC_CFG_INDEX = 2,
        NOC_CFG_IMAGE = 3,
        NOC_CFG_CRC = 4,
        NOC_CFG_VERSION = 5,
        NOC_CFG_BUSY = 6,
        NOC_CFG_OWNER = 7
    } config_status_t;

    typedef enum logic [2:0] {
        NOC_DRAINED = 0,
        NOC_FLUSHED = 1,
        NOC_TIMEOUT = 2,
        NOC_EPOCH_EXHAUSTED = 3
    } lifecycle_status_t;

    typedef enum logic [7:0] {
        NOC_ERROR_NONE = 0,
        NOC_ERROR_BINDING = 1,
        NOC_ERROR_SEQUENCE = 2,
        NOC_ERROR_TIMEOUT = 3,
        NOC_ERROR_TRANSPORT = 4,
        NOC_ERROR_EGRESS = 5,
        NOC_ERROR_EPOCH = 6,
        NOC_ERROR_UNKNOWN = 7
    } error_t;
    // Fixed v1 bindings share one layout; parameterized transport vectors stay local.
    typedef struct packed {
        logic valid;
        logic [15:0] id;
        logic [15:0] generation;
        logic [7:0] epoch;
        logic [7:0] slot;
        logic [7:0] context_id;
        logic [15:0] owner;
        logic [15:0] kernel;
        logic [31:0] package_id;
        logic [7:0] source_node;
        logic [7:0] source_channel;
        logic [7:0] destination_node;
        logic [7:0] destination_channel;
        logic [7:0] classes;
        logic [15:0] messages;
        logic [7:0] budget;
        logic [15:0] reply_flow;
        logic [15:0] initial_sequence;
    } flow_t;

    function automatic flow_t decode_flow(input logic [255:0] record);
        flow_t f;
        f.valid = record[0];
        f.id = record[16:1];
        f.generation = record[32:17];
        f.epoch = record[40:33];
        f.slot = record[48:41];
        f.context_id = record[56:49];
        f.owner = record[79:64];
        f.kernel = record[95:80];
        f.package_id = record[127:96];
        f.source_node = record[135:128];
        f.source_channel = record[143:136];
        f.destination_node = record[151:144];
        f.destination_channel = record[159:152];
        f.classes = record[167:160];
        f.messages = record[183:168];
        f.budget = record[191:184];
        f.reply_flow = record[207:192];
        f.initial_sequence = record[223:208];
        return f;
    endfunction

endpackage
