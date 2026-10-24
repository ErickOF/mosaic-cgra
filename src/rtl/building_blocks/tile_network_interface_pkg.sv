`timescale 1ns / 1ps
`default_nettype none

// Repository-local transport diagnoses. Flit records depend on instance geometry.
package tile_network_interface_pkg;
    localparam int NI_ERROR_WIDTH = 5;

    typedef enum logic {
        FLOW_VALID_READY = 1'b0,
        FLOW_CREDIT = 1'b1
    } flow_control_t;

    typedef enum logic [NI_ERROR_WIDTH-1:0] {
        NI_ERR_NONE = 5'd0,
        NI_ERR_KEEP = 5'd1,
        NI_ERR_CLASS = 5'd2,
        NI_ERR_VC = 5'd3,
        NI_ERR_VC_MAPPING = 5'd4,
        NI_ERR_DESTINATION = 5'd5,
        NI_ERR_CONTEXT = 5'd6,
        NI_ERR_EPOCH = 5'd7,
        NI_ERR_CREDIT = 5'd8,
        NI_ERR_RX_OVERFLOW = 5'd9,
        NI_ERR_FRAGMENT = 5'd10,
        NI_ERR_SIDEBAND = 5'd11,
        NI_ERR_PADDING = 5'd12,
        NI_ERR_PARITY = 5'd13,
        NI_ERR_UNKNOWN = 5'd14,
        NI_ERR_CONFIG = 5'd15,
        NI_ERR_DISABLED = 5'd16
    } interface_error_t;
endpackage
`default_nettype wire
