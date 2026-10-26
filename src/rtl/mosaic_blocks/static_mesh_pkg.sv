`timescale 1ns / 1ps
package static_mesh_pkg;
    typedef enum logic [2:0] {
        MESH_CFG_WRITE = 0,
        MESH_CFG_READ = 1,
        MESH_CFG_VALIDATE = 2,
        MESH_CFG_ACTIVATE = 3,
        MESH_CFG_INVALIDATE = 4,
        MESH_CFG_QUERY = 5
    } cfg_opcode_t;

    typedef enum logic [1:0] {
        MESH_DIR_NORTH = 0,
        MESH_DIR_SOUTH = 1,
        MESH_DIR_EAST = 2,
        MESH_DIR_WEST = 3
    } direction_t;

    typedef enum logic [1:0] {
        MESH_CONNECT_MINIMAL = 0,
        MESH_CONNECT_BALANCED = 1,
        MESH_CONNECT_FLEXIBLE = 2
    } connectivity_t;

    typedef enum logic [7:0] {
        MESH_OK = 0,
        MESH_ERR_UNKNOWN = 1,
        MESH_ERR_CONTEXT = 2,
        MESH_ERR_VERSION = 3,
        MESH_ERR_ACTIVE = 4,
        MESH_ERR_WORD = 5,
        MESH_ERR_INCOMPLETE = 6,
        MESH_ERR_CHECKSUM = 7,
        MESH_ERR_ROUTE = 8,
        MESH_ERR_PHYSICAL = 9,
        MESH_ERR_FANOUT = 10,
        MESH_ERR_KERNEL = 11,
        MESH_ERR_PROOF = 12,
        MESH_ERR_BUSY = 13,
        MESH_ERR_FAULTED = 14,
        MESH_ERR_METADATA = 15,
        MESH_ERR_SCHEDULE = 16,
        MESH_ERR_PARITY = 17,
        MESH_ERR_INTEGRITY = 18,
        MESH_ERR_EPOCH = 19,
        MESH_ERR_COUNTER = 20,
        MESH_ERR_COMMAND = 21
    } error_t;

    typedef enum logic [1:0] {
        MESH_CONTROL_READY = 0,
        MESH_CONTROL_INSTALL = 1,
        MESH_CONTROL_ACK = 2
    } control_phase_t;
endpackage
