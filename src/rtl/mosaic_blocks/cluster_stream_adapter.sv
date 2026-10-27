`timescale 1ns / 1ps
`default_nettype none
// Explicit v1 metadata bridge. The mesh envelope contains its routing prefix,
// the complete 256-bit common payload, and allocation/source identity. The native
// MST prefix is distinct from the BCT false-token bit; insertion/removal is lossless
// because the native MST's reserved upper bits must be zero.
module cluster_stream_adapter #(
    parameter IS_MST = 0,
    parameter TILE_ID = 0
) (
    input wire i_enable,
    input wire [7:0] i_context_id,
    input wire [15:0] i_native_version,
    input wire [15:0] i_route_version,
    input wire [15:0] i_owner_id,
    input wire [15:0] i_kernel_id,
    input wire [31:0] i_package_id,
    input wire [15:0] i_allocation_generation,
    input wire [3:0] i_epoch,
    input wire [3:0] i_mst_epoch,
    input wire i_native_tx_valid,
    output wire o_native_tx_ready,
    input wire [31:0] i_native_tx_data,
    input wire [255:0] i_native_tx_metadata,
    output wire o_mesh_tx_valid,
    input wire i_mesh_tx_ready,
    output wire [31:0] o_mesh_tx_data,
    output logic [511:0] o_mesh_tx_metadata,
    input wire i_mesh_rx_valid,
    output wire o_mesh_rx_ready,
    input wire [31:0] i_mesh_rx_data,
    input wire [511:0] i_mesh_rx_metadata,
    output wire o_native_rx_valid,
    input wire i_native_rx_ready,
    output wire [31:0] o_native_rx_data,
    output logic [255:0] o_native_rx_metadata,
    input wire i_store_valid,
    input wire [133:0] i_store_identity,
    input wire [15:0] i_store_format,
    output wire o_error
);
    logic [255:0] common_tx;
    wire [255:0] common_rx = i_mesh_rx_metadata[64+:256];
    wire [133:0] identity = common_rx[19+:134];
    wire identity_ok = identity == 0 || (identity[32+:16] == i_owner_id &&
        identity[48+:16] == i_kernel_id && identity[64+:32] == i_package_id &&
        identity[96+:2] == i_context_id[1:0] &&
        identity[114+:16] == i_allocation_generation && identity[130+:4] == i_mst_epoch);
    wire tx_ok = (^{i_native_tx_metadata, i_native_tx_data} !== 1'bx) &&
        i_native_tx_metadata[1:0] == i_context_id[1:0] &&
        i_native_tx_metadata[2+:16] == i_native_version &&
        (!IS_MST || (i_native_tx_metadata[255:184] == 0));
    wire envelope_ok = (^{i_mesh_rx_metadata, i_mesh_rx_data} !== 1'bx) &&
        i_mesh_rx_metadata[7:0] == i_context_id &&
        i_mesh_rx_metadata[8+:16] == i_route_version &&
        i_mesh_rx_metadata[24+:16] == i_kernel_id &&
        i_mesh_rx_metadata[40+:4] == i_epoch &&
        i_mesh_rx_metadata[320+:16] == i_owner_id &&
        i_mesh_rx_metadata[336+:32] == i_package_id &&
        i_mesh_rx_metadata[511:376] == 0 && i_mesh_rx_metadata[63:56] == 0;
    wire rx_ok = envelope_ok && (!IS_MST || (identity_ok &&!common_rx[18] &&
        common_rx[255:185] == 0));
    wire destination_ready = !IS_MST || i_store_valid;

    always @* begin
        common_tx = i_native_tx_metadata;

        if (IS_MST) common_tx = {i_native_tx_metadata[254:18], 1'b0,
            i_native_tx_metadata[17:0]};

        o_mesh_tx_metadata = '0;
        o_mesh_tx_metadata[0+:8] = i_context_id;
        o_mesh_tx_metadata[8+:16] = i_route_version;
        o_mesh_tx_metadata[24+:16] = i_kernel_id;
        o_mesh_tx_metadata[40+:4] = i_epoch;
        o_mesh_tx_metadata[44+:4] = common_tx[19+:134] == 0 ? 4'hf : common_tx[153+:4];
        o_mesh_tx_metadata[48+:6] = common_tx[19+:134] == 0 ? 6'd0 : common_tx[175+:6];
        o_mesh_tx_metadata[64+:256] = common_tx;
        o_mesh_tx_metadata[320+:16] = i_owner_id;
        o_mesh_tx_metadata[336+:32] = i_package_id;
        o_mesh_tx_metadata[368+:8] = 8'(TILE_ID);
        o_native_rx_metadata = common_rx;

        if (IS_MST) begin
            o_native_rx_metadata = {1'b0, common_rx[255:19], common_rx[17:0]};
            // Compiler-declared store binding converts a result stream into the
            // admitted destination command's stream; it never guesses command IDs.
            o_native_rx_metadata[18+:134] = i_store_identity;
            o_native_rx_metadata[160+:6] = i_store_format[6+:6];
            o_native_rx_metadata[180+:2] = i_store_format[0+:2];
            o_native_rx_metadata[182+:2] = i_store_format[4+:2];
        end

        o_native_rx_metadata[0+:2] = i_context_id[1:0];
        o_native_rx_metadata[2+:16] = i_native_version;
    end

    assign o_mesh_tx_valid = i_enable && i_native_tx_valid && tx_ok;
    assign o_native_tx_ready = i_enable && i_mesh_tx_ready === 1'b1 && tx_ok;
    assign o_mesh_tx_data = i_native_tx_data;
    assign o_native_rx_valid = i_enable && i_mesh_rx_valid && rx_ok && destination_ready;
    assign o_mesh_rx_ready = i_enable && i_native_rx_ready === 1'b1 && rx_ok && destination_ready;
    assign o_native_rx_data = i_mesh_rx_data;
    assign o_error = i_enable && ((i_native_tx_valid === 1'b1 &&!tx_ok) ||
        (i_mesh_rx_valid === 1'b1 &&!rx_ok));
endmodule
`default_nettype wire
