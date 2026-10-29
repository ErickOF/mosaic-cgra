`timescale 1ns / 1ps
`default_nettype none
// One lossless cluster boundary lane per endpoint. The complete native envelope
// crosses the released TNI as a 640-bit token; five 128-bit flits carry it on VC0.
module array_noc_gateway #(
    parameter SOURCE_NODE = 0,
    parameter DESTINATION_NODE = 1,
    parameter FLOW_ID = 1
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_sequence_clear,
    input wire i_enable,
    input wire [15:0] i_owner,
    input wire [15:0] i_kernel,
    input wire [31:0] i_source_package,
    input wire [31:0] i_destination_package,
    input wire [7:0] i_source_epoch,
    input wire [7:0] i_destination_epoch,
    input wire [7:0] i_context,
    input wire [15:0] i_generation,
    input wire [7:0] i_noc_epoch,
    input wire [3:0] i_mst_epoch,
    input wire [15:0] i_destination_generation,
    input wire [3:0] i_destination_mst_epoch,
    input wire i_cluster_valid,
    output wire o_cluster_ready,
    input wire [31:0] i_cluster_data,
    input wire [511:0] i_cluster_metadata,
    output wire o_tx_valid,
    input wire i_tx_ready,
    output wire [639:0] o_tx_data,
    output wire [63:0] o_tx_user_metadata,
    output wire [15:0] o_tx_packet_id,
    input wire i_rx_valid,
    output wire o_rx_ready,
    input wire [639:0] i_rx_data,
    input wire [79:0] i_rx_keep,
    input wire [7:0] i_rx_error,
    input wire [7:0] i_rx_source,
    output wire o_cluster_valid,
    input wire i_cluster_ready,
    output wire [31:0] o_cluster_data,
    output logic [511:0] o_cluster_metadata,
    output wire o_error
);
    localparam bit PARAMETERS_VALID = ((SOURCE_NODE >= 0 && SOURCE_NODE < 2) === 1'b1) &&
        ((DESTINATION_NODE >= 0 && DESTINATION_NODE < 2) === 1'b1) &&
        ((SOURCE_NODE != DESTINATION_NODE) === 1'b1) &&
        ((FLOW_ID > 0 && FLOW_ID <= 65535) === 1'b1);

    if (!PARAMETERS_VALID) begin : g_invalid
        array_noc_gateway_parameters_must_be_valid invalid_parameters ();
    end

    wire [15:0] sequence_id;
    wire tx_known = ^{i_cluster_data, i_cluster_metadata} !== 1'bx;
    wire tx_identity = tx_known && i_cluster_metadata[320+:16] == i_owner &&
        i_cluster_metadata[24+:16] == i_kernel &&
        i_cluster_metadata[336+:32] == i_source_package &&
        i_cluster_metadata[40+:4] == i_source_epoch[3:0] &&
        i_cluster_metadata[7:0] == i_context;
    // Receiver identity refers to the remote producer. Local package and epoch
    // are translated only after the full allocation group has been authenticated.
    wire [133:0] received_identity = i_rx_data[32+83+:134];
    wire command_namespace = received_identity != 0 &&
        received_identity[32+:16] == i_owner && received_identity[48+:16] == i_kernel &&
        received_identity[64+:32] == i_destination_package &&
        received_identity[96+:2] == i_context[1:0] &&
        received_identity[114+:16] == i_destination_generation &&
        received_identity[130+:4] == i_destination_mst_epoch;
    wire rx_known = ^{i_rx_data, i_rx_keep, i_rx_error, i_rx_source} !== 1'bx;
    wire rx_identity = rx_known && i_rx_data[639:544] == 0 &&
        i_rx_keep == {80{1'b1}} && i_rx_error == 0 &&
        i_rx_source == 8'(DESTINATION_NODE) &&
        i_rx_data[32+320+:16] == i_owner && i_rx_data[32+24+:16] == i_kernel &&
        i_rx_data[32+336+:32] == i_destination_package &&
        i_rx_data[32+40+:4] == i_destination_epoch[3:0] &&
        i_rx_data[32+:8] == i_context;
    assign o_tx_valid = i_enable && i_cluster_valid === 1'b1 && tx_identity && !(&sequence_id);
    assign o_cluster_ready = i_enable && i_tx_ready === 1'b1 && tx_identity && !(&sequence_id);
    assign o_tx_data = {96'd0, i_cluster_metadata, i_cluster_data};
    assign o_tx_user_metadata = {sequence_id, 8'd0, i_noc_epoch, i_generation, 16'(FLOW_ID)};
    assign o_tx_packet_id = sequence_id;
    assign o_cluster_valid = i_enable && i_rx_valid === 1'b1 && rx_identity;
    assign o_rx_ready = i_enable && i_cluster_ready === 1'b1 && rx_identity;
    assign o_cluster_data = i_rx_data[31:0];
    assign o_error = i_enable && ((i_cluster_valid === 1'b1 &&
        (!tx_identity || &sequence_id)) || (i_rx_valid === 1'b1 && !rx_identity));

    always @* begin
        o_cluster_metadata = i_rx_data[32+:512];
        o_cluster_metadata[336+:32] = i_source_package;
        o_cluster_metadata[40+:4] = i_source_epoch[3:0];

        // The common stream command remains opaque except for its declared
        // destination namespace. The native MST still substitutes the admitted
        // store binding after validating this translated producer identity.
        if (command_namespace) begin
            o_cluster_metadata[147+:32] = i_source_package;
            o_cluster_metadata[179+:2] = i_context[1:0];
            o_cluster_metadata[197+:16] = i_generation;
            o_cluster_metadata[213+:4] = i_mst_epoch;
        end
    end

    counter #(.WIDTH(16)) u_sequence (
        .i_clk(i_clk),
        .i_rstb(i_rstb === 1'b1),
        .i_enable(o_tx_valid && i_tx_ready),
        .i_clear(i_sequence_clear),
        .i_load(1'b0),
        .i_direction(1'b0),
        .i_load_value(16'd0),
        .o_count(sequence_id),
        .o_overflow(),
        .o_underflow(),
        .o_terminal()
    );
endmodule
`default_nettype wire
