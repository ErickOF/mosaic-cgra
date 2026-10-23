`timescale 1ns / 1ps

// Local encodings follow the router specification. Parameter-dependent flit
// records stay in the module; no external contracts package is required.
package noc_router_pkg;
    typedef enum logic [2:0] {
        PORT_LOCAL = 3'd0,
        PORT_NORTH = 3'd1,
        PORT_EAST = 3'd2,
        PORT_SOUTH = 3'd3,
        PORT_WEST = 3'd4
    } port_t;
    typedef enum logic {
        FLOW_VALID_READY = 1'b0,
        FLOW_CREDIT = 1'b1
    } flow_control_t;
    typedef enum logic {
        ROUTE_XY = 1'b0,
        ROUTE_YX = 1'b1
    } routing_t;
    typedef enum logic [1:0] {
        BUFFER_PROTECTION_NONE = 2'd0,
        BUFFER_PROTECTION_PARITY = 2'd1,
        BUFFER_PROTECTION_SECDED = 2'd2
    } protection_t;
    typedef enum logic [4:0] {
        ROUTER_ERR_NONE = 5'd0,
        ROUTER_ERR_PORT = 5'd1,
        ROUTER_ERR_RANGE = 5'd2,
        ROUTER_ERR_CLASS = 5'd3,
        ROUTER_ERR_PROTOCOL = 5'd4,
        ROUTER_ERR_EPOCH = 5'd5,
        ROUTER_ERR_CREDIT = 5'd6,
        ROUTER_ERR_CONFIG = 5'd7,
        ROUTER_ERR_CORRECTED = 5'd8,
        ROUTER_ERR_UNCORRECTABLE = 5'd9,
        ROUTER_ERR_UNKNOWN = 5'd10,
        ROUTER_ERR_OVERFLOW = 5'd11,
        ROUTER_ERR_PARITY = 5'd12,
        ROUTER_ERR_OWNERSHIP = 5'd13
    } router_error_t;
endpackage
