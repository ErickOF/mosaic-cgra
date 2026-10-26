`timescale 1ns / 1ps
`default_nettype none

// Cluster-local predicate transport. Existing mesh nodes retain pending multicast
// ownership; skid links bound ready paths and queues own perimeter transactions.
// Endpoint data association and coordinated data-side recovery remain external.
module predicate_network #(
    parameter NETWORK_ROWS = 4,
    parameter NETWORK_COLS = 4,
    parameter CHANNELS_PER_DIRECTION = 1,
    parameter LOCAL_TX_PORTS = 1,
    parameter LOCAL_RX_PORTS = 1,
    parameter PREDICATE_WIDTH = 8,
    parameter PREDICATE_METADATA_WIDTH = 64,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter ASSOCIATION_TAG_WIDTH = 8,
    parameter PRODUCER_ID_WIDTH = 8,
    parameter PREDICATE_EPOCH_WIDTH = 2,
    parameter PREDICATE_CLASS_WIDTH = 4,
    parameter PREDICATE_ERROR_WIDTH = 2,
    parameter ROUTE_PROOF_ID_WIDTH = 32,
    parameter CONNECTIVITY_PROFILE = 1,
    parameter EXPOSE_BOUNDARY_PORTS = 0,
    parameter SUPPORT_MULTICAST = 1,
    parameter MAX_MULTICAST_FANOUT = 4,
    parameter MAX_TREE_DESTINATIONS = 16,
    parameter SUPPORT_SCHEDULE_CHECK = 1,
    parameter SCHEDULE_PERIOD_MAX = 256,
    parameter CHECK_CONTEXT = 1,
    parameter ENABLE_LINK_PARITY = 1,
    parameter SUPPORT_LINK_EXCLUSION = 1,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    localparam int R = (NETWORK_ROWS >= 1 && NETWORK_ROWS <= 8 &&
        (^NETWORK_ROWS !== 1'bx)) ? NETWORK_ROWS : 1,
    localparam int C = (NETWORK_COLS >= 1 && NETWORK_COLS <= 8 &&
        (^NETWORK_COLS !== 1'bx)) ? NETWORK_COLS : 1,
    localparam int H = (CHANNELS_PER_DIRECTION >= 1 && CHANNELS_PER_DIRECTION <= 2 &&
        (^CHANNELS_PER_DIRECTION !== 1'bx)) ? CHANNELS_PER_DIRECTION : 1,
    localparam int TX = (LOCAL_TX_PORTS >= 1 && LOCAL_TX_PORTS <= 4 &&
        (^LOCAL_TX_PORTS !== 1'bx)) ? LOCAL_TX_PORTS : 1,
    localparam int RX = (LOCAL_RX_PORTS >= 1 && LOCAL_RX_PORTS <= 4 &&
        (^LOCAL_RX_PORTS !== 1'bx)) ? LOCAL_RX_PORTS : 1,
    localparam int PV = (PREDICATE_WIDTH >= 1 && PREDICATE_WIDTH <= 16 &&
        (^PREDICATE_WIDTH !== 1'bx)) ? PREDICATE_WIDTH : 1,
    localparam int M = (PREDICATE_METADATA_WIDTH >= 8 && PREDICATE_METADATA_WIDTH <= 512 &&
        (^PREDICATE_METADATA_WIDTH !== 1'bx)) ? PREDICATE_METADATA_WIDTH : 64,
    localparam int CI = (CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH <= 32 &&
        (^CONTEXT_ID_WIDTH !== 1'bx)) ? CONTEXT_ID_WIDTH : 1,
    localparam int V = (CONTEXT_VERSION_WIDTH >= 1 && CONTEXT_VERSION_WIDTH <= 32 &&
        (^CONTEXT_VERSION_WIDTH !== 1'bx)) ? CONTEXT_VERSION_WIDTH : 1,
    localparam int K = (KERNEL_ID_WIDTH >= 1 && KERNEL_ID_WIDTH <= 32 &&
        (^KERNEL_ID_WIDTH !== 1'bx)) ? KERNEL_ID_WIDTH : 1,
    localparam int T = (ASSOCIATION_TAG_WIDTH >= 1 && ASSOCIATION_TAG_WIDTH <= 16 &&
        (^ASSOCIATION_TAG_WIDTH !== 1'bx)) ? ASSOCIATION_TAG_WIDTH : 1,
    localparam int PR = (PRODUCER_ID_WIDTH >= 1 && PRODUCER_ID_WIDTH <= 16 &&
        (^PRODUCER_ID_WIDTH !== 1'bx)) ? PRODUCER_ID_WIDTH : 1,
    localparam int EP = (PREDICATE_EPOCH_WIDTH >= 1 && PREDICATE_EPOCH_WIDTH <= 32 &&
        (^PREDICATE_EPOCH_WIDTH !== 1'bx)) ? PREDICATE_EPOCH_WIDTH : 1,
    localparam int CL = (PREDICATE_CLASS_WIDTH >= 2 && PREDICATE_CLASS_WIDTH <= 8 &&
        (^PREDICATE_CLASS_WIDTH !== 1'bx)) ? PREDICATE_CLASS_WIDTH : 2,
    localparam int ER = (PREDICATE_ERROR_WIDTH >= 1 && PREDICATE_ERROR_WIDTH <= 8 &&
        (^PREDICATE_ERROR_WIDTH !== 1'bx)) ? PREDICATE_ERROR_WIDTH : 1,
    localparam int P = (ROUTE_PROOF_ID_WIDTH >= 32 && ROUTE_PROOF_ID_WIDTH <= 64 &&
        (^ROUTE_PROOF_ID_WIDTH !== 1'bx)) ? ROUTE_PROOF_ID_WIDTH : 32,
    localparam int PM = (SCHEDULE_PERIOD_MAX >= 1 && SCHEDULE_PERIOD_MAX <= 256 &&
        (^SCHEDULE_PERIOD_MAX !== 1'bx)) ? SCHEDULE_PERIOD_MAX : 1,
    localparam int N = R * C,
    localparam int I = TX + 4 * H,
    localparam int O = RX + 4 * H,
    localparam int D = 2 * PV,
    localparam int B = 2 * H * (R + C),
    localparam int IL = 2 * H * (R * (C - 1) + (R - 1) * C),
    localparam int L = IL + (EXPOSE_BOUNDARY_PORTS === 1 ? 2 * B : 0),
    localparam int LB = L > 0 ? L : 1,
    localparam int LI = L > 1 ? $clog2(L) : 1,
    localparam int LX = $clog2(LB + 1),
    localparam int NI = N > 1 ? $clog2(N) : 1,
    localparam int S = $clog2(I),
    localparam int OS = $clog2(O),
    localparam int RES = N * I,
    localparam int HW = $clog2(RES + 3),
    localparam int TW = $clog2(N * RX + 1),
    localparam int PW = $clog2(PM + 1),
    localparam int RI = N * O * (1 + S),
    localparam int REQ = CI + V + K + EP + PR + T + CL + ER,
    localparam int BODY = RI + LB + LB * PM + PW + CI + V + K + EP,
    localparam int IMAGE = BODY + P,
    localparam int COUNTERS = 32 + 4 * N * (TX + RX) + 4 * LB + 4 * N + N * RX,
    localparam int CW = $clog2(COUNTERS + N + 1),
    parameter NODE_PRESENT_MASK = {N{1'b1}},
    parameter LINK_PRESENT_MASK = default_links(),
    parameter NODE_CONNECTIVITY_MASKS = default_connectivity()
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_enable,
    input wire i_drain,
    input wire i_flush,
    input wire i_error_clear,
    input wire i_cfg_prepare_valid,
    input wire i_cfg_commit_valid,
    input wire i_cfg_abort,
    input wire i_link_fault_valid,
    input wire i_counter_read,
    input wire i_boundary_isolate,
    input wire i_test_enable,
    input wire i_scan_enable,
    input wire i_schedule_pause,
    output wire o_idle,
    output wire o_quiescent,
    output wire o_drained,
    output wire o_flush_completed,
    output wire o_cfg_prepare_ready,
    output wire o_cfg_prepared,
    output wire o_cfg_prepare_rejected,
    output wire o_cfg_commit_ready,
    output wire o_cfg_committed,
    output wire o_cfg_aborted,
    output wire o_active_context_valid,
    output wire o_shadow_valid,
    output wire o_link_fault_ready,
    output wire o_active_link_fault,
    output wire o_error,
    output wire o_counter_valid,
    output wire o_boundary_isolated,
    input wire [N*TX-1:0] i_pred_tx_valid,
    input wire [N*TX*PV-1:0] i_pred_tx_value,
    input wire [N*TX*PV-1:0] i_pred_tx_lane_valid,
    input wire [N*TX*M-1:0] i_pred_tx_metadata,
    output wire [N*RX-1:0] o_pred_rx_valid,
    output wire [N*RX*PV-1:0] o_pred_rx_value,
    output wire [N*RX*PV-1:0] o_pred_rx_lane_valid,
    output wire [N*RX*M-1:0] o_pred_rx_metadata,
    input wire [B-1:0] i_boundary_pred_valid,
    input wire [B*PV-1:0] i_boundary_pred_value,
    input wire [B*PV-1:0] i_boundary_pred_lane_valid,
    input wire [B*M-1:0] i_boundary_pred_metadata,
    input wire [B-1:0] i_boundary_pred_parity,
    output wire [B-1:0] o_boundary_pred_valid,
    output wire [B*PV-1:0] o_boundary_pred_value,
    output wire [B*PV-1:0] o_boundary_pred_lane_valid,
    output wire [B*M-1:0] o_boundary_pred_metadata,
    output wire [B-1:0] o_boundary_pred_parity,
    output wire [N*TX-1:0] o_pred_tx_ready,
    input wire [N*RX-1:0] i_pred_rx_ready,
    output wire [B-1:0] o_boundary_pred_ready,
    input wire [B-1:0] i_boundary_pred_ready,
    input wire [RI-1:0] i_cfg_route_image,
    input wire [LB-1:0] i_cfg_schedule_enable,
    input wire [PW-1:0] i_cfg_schedule_period,
    input wire [LB*PM-1:0] i_cfg_schedule_slot_image,
    input wire [CI-1:0] i_cfg_context_id,
    input wire [V-1:0] i_cfg_context_version,
    input wire [K-1:0] i_cfg_kernel_id,
    input wire [EP-1:0] i_cfg_epoch,
    input wire [P-1:0] i_cfg_route_proof_id,
    input wire [CI-1:0] i_cfg_commit_context_id,
    input wire [V-1:0] i_cfg_commit_context_version,
    input wire [LB-1:0] i_link_fault_mask,
    input wire [N*RX-1:0] i_endpoint_alignment_error,
    input wire [N*RX*T-1:0] i_endpoint_alignment_expected_tag,
    input wire [N*RX*T-1:0] i_endpoint_alignment_observed_tag,
    input wire [CW-1:0] i_counter_index,
    output wire [7:0] o_cfg_prepare_error_code,
    output wire [CI-1:0] o_active_context_id,
    output wire [V-1:0] o_active_context_version,
    output wire [K-1:0] o_active_kernel_id,
    output wire [EP-1:0] o_active_epoch,
    output wire [LB-1:0] o_faulted_link_mask,
    output wire [N*I-1:0] o_node_buffered,
    output wire [LB-1:0] o_link_transfer,
    output wire [N*TX-1:0] o_injection_stall,
    output wire [N*RX-1:0] o_ejection_stall,
    output wire [N-1:0] o_multicast_event,
    output wire [LB-1:0] o_schedule_violation,
    output wire [LB-1:0] o_parity_error_event,
    output wire [N*RX-1:0] o_alignment_error_event,
    output wire [N-1:0] o_node_clock_enable,
    output wire [7:0] o_error_code,
    output wire [NI-1:0] o_error_node,
    output wire [LI-1:0] o_error_link,
    output wire [PR-1:0] o_error_source,
    output wire [CI-1:0] o_error_context_id,
    output wire [V-1:0] o_error_context_version,
    output wire [K-1:0] o_error_kernel_id,
    output wire [EP-1:0] o_error_epoch,
    output wire [T-1:0] o_error_tag,
    output wire [T-1:0] o_error_expected_tag,
    output wire [31:0] o_topology_id,
    output wire [31:0] o_counter_value
);
    import predicate_network_pkg::*;

    // Internal edges are horizontal (east, west), then vertical (south, north).
    // Channels increase inside each edge. Boundary input/output pairs follow.
    function automatic int internal_link(
        input int rows,
        input int cols,
        input int channels,
        input int node,
        input int direction,
        input int channel
    );
        int row;
        int col;
        int offset;
        row = node / cols;
        col = node % cols;
        offset = 2 * channels * rows * (cols - 1);

        case (direction)
            0: return row > 0 ?
                offset + 2 * (((row - 1) * cols + col) * channels + channel) + 1 : -1;
            1: return row + 1 < rows ? offset + 2 * ((row * cols + col) * channels + channel) : -1;
            2: return col + 1 < cols ? 2 * ((row * (cols - 1) + col) * channels + channel) : -1;
            3: return col > 0 ? 2 * ((row * (cols - 1) + col - 1) * channels + channel) + 1 : -1;
            default: return -1;
        endcase
    endfunction

    function automatic int neighbor(
        input int rows,
        input int cols,
        input int node,
        input int direction
    );
        case (direction)
            0: return node / cols > 0 ? node - cols : -1;
            1: return node / cols + 1 < rows ? node + cols : -1;
            2: return node % cols + 1 < cols ? node + 1 : -1;
            3: return node % cols > 0 ? node - 1 : -1;
            default: return -1;
        endcase
    endfunction

    function automatic int boundary_port(
        input int rows,
        input int cols,
        input int channels,
        input int node,
        input int direction,
        input int channel
    );
        case (direction)
            0: return node / cols == 0 ? node % cols * channels + channel : -1;
            1: return node / cols == rows - 1 ? (cols + node % cols) * channels + channel : -1;
            3: return node % cols == 0 ? (2 * cols + node / cols) * channels + channel : -1;
            2: return node % cols == cols - 1 ?
                (2 * cols + rows + node / cols) * channels + channel : -1;
            default: return -1;
        endcase
    endfunction

    function automatic int output_link(
        input int node,
        input int output_port
    );
        int direction;
        int channel;
        int link_index;
        int boundary_index;

        if (output_port < RX) return L;

        direction = (output_port - RX) / H;
        channel = (output_port - RX) % H;
        link_index = internal_link(R, C, H, node, direction, channel);

        if (link_index >= 0) return link_index;

        boundary_index = boundary_port(R, C, H, node, direction, channel);

        return EXPOSE_BOUNDARY_PORTS == 1 && boundary_index >= 0 ?
            IL + 2 * boundary_index + 1 : L;
    endfunction

    function automatic int input_link(
        input int node,
        input int input_port
    );
        int direction;
        int channel;
        int peer;
        int boundary_index;

        if (input_port < TX) return L;

        direction = (input_port - TX) / H;
        channel = (input_port - TX) % H;
        peer = neighbor(R, C, node, direction);

        if (peer >= 0) return internal_link(R, C, H, peer, direction ^ 1, channel);

        boundary_index = boundary_port(R, C, H, node, direction, channel);

        return EXPOSE_BOUNDARY_PORTS == 1 && boundary_index >= 0 ?
            IL + 2 * boundary_index : L;
    endfunction

    function automatic logic [LB-1:0] default_links();
        int node;
        int d;
        int k;
        logic [LB-1:0] result;
        int peer;
        int link_index;
        result = '0;

        for (node = 0; node < N; node++) begin
            for (d = 0; d < 4; d++) begin
                peer = neighbor(R, C, node, d);

                for (k = 0; k < H; k++) begin
                    link_index = output_link(node, RX + d * H + k);

                    if (NODE_PRESENT_MASK[node] && (peer < 0 || NODE_PRESENT_MASK[peer]) &&
                        link_index < L) result[link_index] = 1'b1;

                    link_index = input_link(node, TX + d * H + k);

                    if (NODE_PRESENT_MASK[node] && (peer < 0 || NODE_PRESENT_MASK[peer]) &&
                        link_index < L) result[link_index] = 1'b1;
                end
            end
        end

        return result;
    endfunction

    function automatic logic [N*O*I-1:0] default_connectivity();
        int node;
        int o;
        int i;
        logic [N*O*I-1:0] result;
        int incoming;
        int outgoing;
        int ilink;
        int olink;
        logic input_present;
        logic output_present;
        result = '0;

        for (node = 0; node < N; node++) begin
            for (o = 0; o < O; o++) begin
                for (i = 0; i < I; i++) begin
                    ilink = input_link(node, i);
                    olink = output_link(node, o);
                    input_present = i < TX || (ilink < L && LINK_PRESENT_MASK[ilink]);
                    output_present = o < RX || (olink < L && LINK_PRESENT_MASK[olink]);
                    incoming = i < TX ? -1 : (i - TX) / H;
                    outgoing = o < RX ? -1 : (o - RX) / H;

                    if (NODE_PRESENT_MASK[node] && input_present && output_present &&
                        (incoming < 0 || outgoing < 0 || outgoing == (incoming ^ 1) ||
                        (CONNECTIVITY_PROFILE >= 1 && outgoing != incoming)))
                        result[node*O*I+o*I+i] = 1'b1;
                end
            end
        end

        return result;
    endfunction

    function automatic logic topology_valid();
        int n;
        int o;
        int i;
        logic [LB-1:0] possible;
        int ilink;
        int olink;
        possible = default_links();

        if ((LINK_PRESENT_MASK & ~possible) != '0) return 1'b0;

        for (n = 0; n < N; n++) begin
            for (o = 0; o < O; o++) begin
                for (i = 0; i < I; i++) begin
                    ilink = input_link(n, i);
                    olink = output_link(n, o);

                    if (NODE_CONNECTIVITY_MASKS[n*O*I+o*I+i] &&
                        (!NODE_PRESENT_MASK[n] || (i >= TX &&
                            (ilink >= L ||!LINK_PRESENT_MASK[ilink])) ||
                        (o >= RX && (olink >= L ||!LINK_PRESENT_MASK[olink])))) return 1'b0;
                end
            end
        end

        return 1'b1;
    endfunction

    function automatic int source_resource(input int link_id);
        int n;
        int o;

        for (n = 0; n < N; n++)
            for (o = RX; o < O; o++)
                if (output_link(n, o) == link_id) return n * O + o;

        return 0;
    endfunction

    function automatic int destination_resource(input int link_id);
        int n;
        int i;

        for (n = 0; n < N; n++)
            for (i = TX; i < I; i++)
                if (input_link(n, i) == link_id) return n * I + i;

        return 0;
    endfunction

    function automatic int row_count(input int node);
        int o;
        int count;
        count = 0;

        for (o = 0; o < O; o++)
            if (|NODE_CONNECTIVITY_MASKS[node*O*I+o*I+:I]) count++;

        return count;
    endfunction

    function automatic int row_rank(
        input int node,
        input int port_index
    );
        int o;
        int count;
        count = 0;

        for (o = 0; o < port_index; o++)
            if (|NODE_CONNECTIVITY_MASKS[node*O*I+o*I+:I]) count++;

        return count;
    endfunction

    function automatic logic [O*I-1:0] compact_matrix(input int node);
        int o;
        logic [O*I-1:0] matrix;
        matrix = '0;

        for (o = 0; o < O; o++)
            if (|NODE_CONNECTIVITY_MASKS[node*O*I+o*I+:I])
                matrix[row_rank(node, o)*I+:I] =
                    NODE_CONNECTIVITY_MASKS[node*O*I+o*I+:I];

        return matrix;
    endfunction

    function automatic logic [31:0] fingerprint();
        int b;
        logic [31:0] value;
        value = 32'h504e0101;
        value = (value ^ 32'(NETWORK_ROWS)) * 32'd16777619;
        value = (value ^ 32'(NETWORK_COLS)) * 32'd16777619;
        value = (value ^ 32'(CHANNELS_PER_DIRECTION)) * 32'd16777619;
        value = (value ^ 32'(LOCAL_TX_PORTS)) * 32'd16777619;
        value = (value ^ 32'(LOCAL_RX_PORTS)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_METADATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_VERSION_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(KERNEL_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(ASSOCIATION_TAG_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PRODUCER_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_EPOCH_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_CLASS_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_ERROR_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(ROUTE_PROOF_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONNECTIVITY_PROFILE)) * 32'd16777619;
        value = (value ^ 32'(EXPOSE_BOUNDARY_PORTS)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_MULTICAST)) * 32'd16777619;
        value = (value ^ 32'(MAX_MULTICAST_FANOUT)) * 32'd16777619;
        value = (value ^ 32'(MAX_TREE_DESTINATIONS)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_SCHEDULE_CHECK)) * 32'd16777619;
        value = (value ^ 32'(SCHEDULE_PERIOD_MAX)) * 32'd16777619;
        value = (value ^ 32'(CHECK_CONTEXT)) * 32'd16777619;
        value = (value ^ 32'(ENABLE_LINK_PARITY)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_LINK_EXCLUSION)) * 32'd16777619;
        value = (value ^ 32'(CONTROL_PROTECTION)) * 32'd16777619;
        value = (value ^ 32'(ASYNC_RESET)) * 32'd16777619;

        for (b = 0; b < N; b++) value = (value ^ 32'(NODE_PRESENT_MASK[b])) * 32'd16777619;

        for (b = 0; b < L; b++) value = (value ^ 32'(LINK_PRESENT_MASK[b])) * 32'd16777619;

        for (b = 0; b < N * O * I; b++)
            value = (value ^ 32'(NODE_CONNECTIVITY_MASKS[b])) * 32'd16777619;

        return value;
    endfunction

    localparam logic [31:0] TOPOLOGY_ID = fingerprint();
    assign o_topology_id = TOPOLOGY_ID;
    localparam bit PARAMETERS_VALID =
        ((NETWORK_ROWS >= 1 && NETWORK_ROWS <= 8) === 1'b1) && (^NETWORK_ROWS !== 1'bx) &&
        ((NETWORK_COLS >= 1 && NETWORK_COLS <= 8) === 1'b1) && (^NETWORK_COLS !== 1'bx) &&
        ((CHANNELS_PER_DIRECTION >= 1 && CHANNELS_PER_DIRECTION <= 2) === 1'b1) &&
            (^CHANNELS_PER_DIRECTION !== 1'bx) &&
        ((LOCAL_TX_PORTS >= 1 && LOCAL_TX_PORTS <= 4) === 1'b1) && (^LOCAL_TX_PORTS !== 1'bx) &&
        ((LOCAL_RX_PORTS >= 1 && LOCAL_RX_PORTS <= 4) === 1'b1) && (^LOCAL_RX_PORTS !== 1'bx) &&
        ((PREDICATE_WIDTH >= 1 && PREDICATE_WIDTH <= 16) === 1'b1) && (^PREDICATE_WIDTH !== 1'bx) &&
        ((PREDICATE_METADATA_WIDTH >= 8 && PREDICATE_METADATA_WIDTH <= 512) === 1'b1) &&
            (^PREDICATE_METADATA_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH <= 32) === 1'b1) &&
            (^CONTEXT_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_VERSION_WIDTH >= 1 && CONTEXT_VERSION_WIDTH <= 32) === 1'b1) &&
            (^CONTEXT_VERSION_WIDTH !== 1'bx) &&
        ((KERNEL_ID_WIDTH >= 1 && KERNEL_ID_WIDTH <= 32) === 1'b1) && (^KERNEL_ID_WIDTH !== 1'bx) &&
        ((ASSOCIATION_TAG_WIDTH >= 1 && ASSOCIATION_TAG_WIDTH <= 16) === 1'b1) &&
            (^ASSOCIATION_TAG_WIDTH !== 1'bx) &&
        ((PRODUCER_ID_WIDTH >= 1 && PRODUCER_ID_WIDTH <= 16) === 1'b1) &&
            (^PRODUCER_ID_WIDTH !== 1'bx) &&
        ((PREDICATE_EPOCH_WIDTH >= 1 && PREDICATE_EPOCH_WIDTH <= 32) === 1'b1) &&
            (^PREDICATE_EPOCH_WIDTH !== 1'bx) &&
        ((PREDICATE_CLASS_WIDTH >= 2 && PREDICATE_CLASS_WIDTH <= 8) === 1'b1) &&
            (^PREDICATE_CLASS_WIDTH !== 1'bx) &&
        ((PREDICATE_ERROR_WIDTH >= 1 && PREDICATE_ERROR_WIDTH <= 8) === 1'b1) &&
            (^PREDICATE_ERROR_WIDTH !== 1'bx) &&
        ((ROUTE_PROOF_ID_WIDTH >= 32 && ROUTE_PROOF_ID_WIDTH <= 64) === 1'b1) &&
            (^ROUTE_PROOF_ID_WIDTH !== 1'bx) &&
        ((SCHEDULE_PERIOD_MAX >= 1 && SCHEDULE_PERIOD_MAX <= 256) === 1'b1) &&
            (^SCHEDULE_PERIOD_MAX !== 1'bx) &&
        (EXPOSE_BOUNDARY_PORTS === 0 || EXPOSE_BOUNDARY_PORTS === 1) &&
        (SUPPORT_MULTICAST === 0 || SUPPORT_MULTICAST === 1) &&
        (SUPPORT_SCHEDULE_CHECK === 0 || SUPPORT_SCHEDULE_CHECK === 1) &&
        (CHECK_CONTEXT === 0 || CHECK_CONTEXT === 1) &&
        (ENABLE_LINK_PARITY === 0 || ENABLE_LINK_PARITY === 1) &&
        (SUPPORT_LINK_EXCLUSION === 0 || SUPPORT_LINK_EXCLUSION === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1) &&
        (CONNECTIVITY_PROFILE === 0 || CONNECTIVITY_PROFILE === 1 || CONNECTIVITY_PROFILE === 2) &&
        (CONTROL_PROTECTION === 0 || CONTROL_PROTECTION === 1 || CONTROL_PROTECTION === 2) &&
        (CONNECTIVITY_PROFILE != 0 || (PV == 1 && SUPPORT_MULTICAST == 0)) &&
        M % 8 == 0 && M >= REQ &&
        MAX_MULTICAST_FANOUT > 0 && MAX_MULTICAST_FANOUT <= O &&
        MAX_TREE_DESTINATIONS > 0 && MAX_TREE_DESTINATIONS <= N * RX &&
        (^MAX_MULTICAST_FANOUT !== 1'bx) && (^MAX_TREE_DESTINATIONS !== 1'bx) &&
        (64'd1 << PR) >= 64'(N * TX + (EXPOSE_BOUNDARY_PORTS ? B : 0)) &&
        $bits(NODE_PRESENT_MASK) == N && (^NODE_PRESENT_MASK !== 1'bx) &&
        $bits(LINK_PRESENT_MASK) == LB && (^LINK_PRESENT_MASK !== 1'bx) &&
        $bits(NODE_CONNECTIVITY_MASKS) == N * O * I && (^NODE_CONNECTIVITY_MASKS !== 1'bx) &&
        topology_valid();

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        predicate_network_parameters_must_be_valid invalid_parameters ();
    end else begin : g_network
        localparam int PKT = D + M + 1;
        localparam int BOUNDARY_BUFFER_DEPTH = 1;
        wire run = i_reset_n === 1'b1;
        wire ingress;
        wire transport;
        wire install;
        wire flush_all;
        wire route_check;
        wire configuration_busy;
        wire schedule_check;
        wire [31:0] tick;
        wire [CI-1:0] install_context;
        wire [RI-1:0] active_route;
        wire [LB-1:0] schedule_enable;
        wire [LB*PM-1:0] slots;
        wire [PW-1:0] period;
        wire [RES*HW-1:0] depths;
        wire [N*RX-1:0] quarantine;
        wire [RES*LX-1:0] input_links;
        wire [N*O*LX-1:0] output_links;
        wire [RES*32-1:0] input_source;
        wire [N*O*HW-1:0] output_target;
        wire [RES-1:0] buffered;
        wire [RES-1:0] raw_input_valid;
        logic [RES-1:0] input_valid;
        wire [RES-1:0] raw_input_ready;
        logic [RES-1:0] input_ready;
        wire [RES*D-1:0] raw_input_data;
        logic [RES*D-1:0] input_data;
        wire [RES*M-1:0] raw_input_metadata;
        logic [RES*M-1:0] input_metadata;
        wire [N*O-1:0] raw_output_valid;
        logic [N*O-1:0] output_valid;
        wire [N*O-1:0] raw_output_ready;
        logic [N*O-1:0] output_ready;
        wire [N*O*D-1:0] raw_output_data;
        logic [N*O*D-1:0] output_data;
        wire [N*O*M-1:0] raw_output_metadata;
        logic [N*O*M-1:0] output_metadata;
        wire [N-1:0] node_idle;
        wire [N-1:0] node_bad;
        wire [N-1:0] node_error;
        wire [N-1:0] node_match;
        wire [N-1:0] node_ready;
        wire [N-1:0] multicast;
        wire [LB-1:0] link_idle;
        wire [LB-1:0] link_bad;
        wire [LB-1:0] parity_bad;
        wire [LB-1:0] link_transfer;
        wire [D+M-1:0] observed [LB];
        wire [B-1:0] boundary_bad;
        wire [2*B-1:0] boundary_idle;
        wire [N*TX+B-1:0] metadata_bad;
        wire [2*B-1:0] boundary_stall;
        wire [N*TX-1:0] injection_stall;
        wire [N*RX-1:0] ejection_stall;
        wire [LB-1:0] parity_seen;
        wire parity_seen_bad;
        wire [LB-1:0] parity_pulse = parity_bad & ~parity_seen;
        wire [LB-1:0] next_parity_seen = flush_all || i_error_clear === 1'b1 ?
            '0 : parity_seen | parity_bad;
        wire integrity_bad = (|node_bad) || (|link_bad) || (|boundary_bad) || parity_seen_bad;
        wire all_idle = (&node_idle) && (&link_idle) && (&boundary_idle);
        logic [7:0] runtime_code;
        logic [NI-1:0] runtime_node;
        logic [LI-1:0] runtime_link;
        logic [PR-1:0] runtime_source;
        logic [T-1:0] runtime_tag;
        logic [T-1:0] runtime_expected_tag;
        logic [LB-1:0] schedule_violation;
        wire [COUNTERS-1:0] counter_overflow;
        wire [N*RX-1:0] alignment_event;
        wire [N*TX*D-1:0] i_tile_tx_data;
        wire [N*RX*D-1:0] o_tile_rx_data;
        wire [N*RX-1:0] i_tile_rx_ready;
        wire [B*D-1:0] i_boundary_rx_data;
        wire [B*D-1:0] o_boundary_tx_data;
        wire [N*RX*T-1:0] expected_tags = i_endpoint_alignment_expected_tag;
        wire [N*RX*T-1:0] observed_tags = i_endpoint_alignment_observed_tag;
        assign o_idle = run && all_idle &&!integrity_bad;

        always @* begin
            input_valid = raw_input_valid;
            input_ready = raw_input_ready;
            input_data = raw_input_data;
            input_metadata = raw_input_metadata;
            output_valid = raw_output_valid;
            output_ready = raw_output_ready;
            output_data = raw_output_data;
            output_metadata = raw_output_metadata;
        end

        // Inactive unknown value lanes canonicalize to zero. Known one bits in
        // inactive lanes are malformed; true and false active lanes are distinct.
        function automatic logic [D-1:0] canonical(input logic [D-1:0] packet);
            return {packet[PV+:PV], packet[0+:PV] & packet[PV+:PV]};
        endfunction

        function automatic logic [7:0] token_error(
        input logic [D-1:0] packet,
        input logic [M-1:0] meta,
        input logic [PR-1:0] producer
    );
            logic [PV-1:0] mask;
            int pred_class;
            mask = packet[PV+:PV];
            pred_class = int'(meta[CI+V+K+EP+PR+T+:CL]);

            if (^meta === 1'bx || ^mask === 1'bx) return PRED_NET_ERR_UNKNOWN;

            if (CHECK_CONTEXT) begin
                if (meta[CI+V+K+:EP] != o_active_epoch) return PRED_NET_ERR_EPOCH;

                if (meta[0+:CI] != o_active_context_id ||
                    meta[CI+:V] != o_active_context_version ||
                    meta[CI+V+:K] != o_active_kernel_id) return PRED_NET_ERR_CONTEXT;

                if (meta[CI+V+K+EP+:PR] != producer) return PRED_NET_ERR_PRODUCER;
            end

            if (pred_class > int'(PRED_CLASS_EMPTY_VECTOR) ||
                ((pred_class == int'(PRED_CLASS_SCALAR) ||
                pred_class == int'(PRED_CLASS_EMPTY_SCALAR)) && (mask >> 1) != 0) ||
                (mask == 0 && pred_class < int'(PRED_CLASS_EMPTY_SCALAR)))
                return PRED_NET_ERR_LANE;

            for (int k = 0; k < PV; k++) begin
                if (!mask[k] && packet[k] === 1'b1) return PRED_NET_ERR_LANE;

                if (mask[k] && packet[k] !== 1'b0 && packet[k] !== 1'b1)
                    return PRED_NET_ERR_UNKNOWN;
            end

            return PRED_NET_OK;
        endfunction

        function automatic logic legal_metadata(
        input logic [D-1:0] packet,
        input logic [M-1:0] meta,
        input logic [PR-1:0] producer
    );

            return token_error(packet, meta, producer) == PRED_NET_OK;
        endfunction

        for (genvar j = 0; j < N * TX; j++) begin : g_pack_tx
            assign i_tile_tx_data[j*D+:D] =
                {i_pred_tx_lane_valid[j*PV+:PV], i_pred_tx_value[j*PV+:PV]};
        end

        for (genvar j = 0; j < N * RX; j++) begin : g_unpack_rx
            assign alignment_event[j] = run && o_active_context_valid &&!flush_all &&
                active_route[j/RX*O+j%RX] && i_endpoint_alignment_error[j] !== 1'b0 &&
                (i_endpoint_alignment_error[j] !== 1'b1 ||
                expected_tags[j*T+:T] !== observed_tags[j*T+:T] ||
                ^expected_tags[j*T+:T] === 1'bx || ^observed_tags[j*T+:T] === 1'bx);
            assign i_tile_rx_ready[j] = i_pred_rx_ready[j] === 1'b1 &&
                !quarantine[j] &&!alignment_event[j];
            assign o_pred_rx_value[j*PV+:PV] = o_tile_rx_data[j*D+:PV];
            assign o_pred_rx_lane_valid[j*PV+:PV] = o_tile_rx_data[j*D+PV+:PV];
        end

        for (genvar b = 0; b < B; b++) begin : g_pack_boundary
            assign i_boundary_rx_data[b*D+:D] =
                {i_boundary_pred_lane_valid[b*PV+:PV], i_boundary_pred_value[b*PV+:PV]};
            assign o_boundary_pred_value[b*PV+:PV] = o_boundary_tx_data[b*D+:PV];
            assign o_boundary_pred_lane_valid[b*PV+:PV] = o_boundary_tx_data[b*D+PV+:PV];
        end

        predicate_network_control #(
            .N(N),
            .I(I),
            .O(O),
            .TX(TX),
            .RX(RX),
            .CI(CI),
            .V(V),
            .K(K),
            .T(T),
            .PR(PR),
            .EP(EP),
            .P(P),
            .PM(PM),
            .IL(IL),
            .L(L),
            .LB(LB),
            .LI(LI),
            .LX(LX),
            .NI(NI),
            .S(S),
            .RES(RES),
            .HW(HW),
            .TW(TW),
            .PW(PW),
            .RI(RI),
            .BODY(BODY),
            .SUPPORT_MULTICAST(SUPPORT_MULTICAST),
            .MAX_MULTICAST_FANOUT(MAX_MULTICAST_FANOUT),
            .MAX_TREE_DESTINATIONS(MAX_TREE_DESTINATIONS),
            .SUPPORT_SCHEDULE_CHECK(SUPPORT_SCHEDULE_CHECK),
            .SUPPORT_LINK_EXCLUSION(SUPPORT_LINK_EXCLUSION),
            .CONTROL_PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET),
            .TOPOLOGY_ID(TOPOLOGY_ID)
        ) u_control (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_enable(i_enable),
            .i_drain(i_drain),
            .i_flush(i_flush),
            .i_error_clear(i_error_clear),
            .i_cfg_prepare_valid(i_cfg_prepare_valid),
            .i_cfg_commit_valid(i_cfg_commit_valid),
            .i_cfg_abort(i_cfg_abort),
            .i_link_fault_valid(i_link_fault_valid),
            .i_boundary_isolate(i_boundary_isolate),
            .i_test_enable(i_test_enable),
            .i_scan_enable(i_scan_enable),
            .i_schedule_pause(i_schedule_pause),
            .o_quiescent(o_quiescent),
            .o_drained(o_drained),
            .o_flush_completed(o_flush_completed),
            .o_cfg_prepare_ready(o_cfg_prepare_ready),
            .o_cfg_prepared(o_cfg_prepared),
            .o_cfg_prepare_rejected(o_cfg_prepare_rejected),
            .o_cfg_commit_ready(o_cfg_commit_ready),
            .o_cfg_committed(o_cfg_committed),
            .o_cfg_aborted(o_cfg_aborted),
            .o_active_context_valid(o_active_context_valid),
            .o_shadow_valid(o_shadow_valid),
            .o_link_fault_ready(o_link_fault_ready),
            .o_active_link_fault(o_active_link_fault),
            .o_error(o_error),
            .o_boundary_isolated(o_boundary_isolated),
            .i_cfg_route_image(i_cfg_route_image),
            .i_cfg_schedule_enable(i_cfg_schedule_enable),
            .i_cfg_schedule_period(i_cfg_schedule_period),
            .i_cfg_schedule_slot_image(i_cfg_schedule_slot_image),
            .i_cfg_context_id(i_cfg_context_id),
            .i_cfg_context_version(i_cfg_context_version),
            .i_cfg_kernel_id(i_cfg_kernel_id),
            .i_cfg_epoch(i_cfg_epoch),
            .i_cfg_route_proof_id(i_cfg_route_proof_id),
            .i_cfg_commit_context_id(i_cfg_commit_context_id),
            .i_cfg_commit_context_version(i_cfg_commit_context_version),
            .i_link_fault_mask(i_link_fault_mask),
            .o_cfg_prepare_error_code(o_cfg_prepare_error_code),
            .o_active_context_id(o_active_context_id),
            .o_active_context_version(o_active_context_version),
            .o_active_kernel_id(o_active_kernel_id),
            .o_active_epoch(o_active_epoch),
            .o_faulted_link_mask(o_faulted_link_mask),
            .o_error_code(o_error_code),
            .o_error_node(o_error_node),
            .o_error_link(o_error_link),
            .o_error_source(o_error_source),
            .o_error_context_id(o_error_context_id),
            .o_error_context_version(o_error_context_version),
            .o_error_kernel_id(o_error_kernel_id),
            .o_error_epoch(o_error_epoch),
            .o_error_tag(o_error_tag),
            .o_error_expected_tag(o_error_expected_tag),
            .i_all_idle(all_idle),
            .i_nodes_ready(&node_ready),
            .i_nodes_match(&node_match),
            .i_integrity_bad(integrity_bad),
            .i_runtime_code(runtime_code),
            .i_runtime_node(runtime_node),
            .i_runtime_link(runtime_link),
            .i_runtime_source(runtime_source),
            .i_runtime_tag(runtime_tag),
            .i_runtime_expected_tag(runtime_expected_tag),
            .i_alignment_event(alignment_event),
            .i_connectivity(NODE_CONNECTIVITY_MASKS),
            .i_link_present(LINK_PRESENT_MASK),
            .i_input_source(input_source),
            .i_output_target(output_target),
            .i_input_links(input_links),
            .i_output_links(output_links),
            .o_route(active_route),
            .o_schedule_enable(schedule_enable),
            .o_slots(slots),
            .o_period(period),
            .o_depths(depths),
            .o_install_context(install_context),
            .o_quarantine(quarantine),
            .o_ingress(ingress),
            .o_transport(transport),
            .o_install(install),
            .o_flush(flush_all),
            .o_route_check(route_check),
            .o_tick(tick),
            .o_schedule_check(schedule_check),
            .o_configuration_busy(configuration_busy)
        );

        for (genvar n = 0; n < N; n++) begin : g_node
            localparam int CO = row_count(n);

            for (genvar i = 0; i < I; i++) begin : g_input_map
                assign input_links[(n*I+i)*LX+:LX] = LX'(input_link(n, i));
                assign input_source[(n*I+i)*32+:32] = 32'(
                    input_link(n, i) < IL ? source_resource(input_link(n, i)) : N * O);
            end

            for (genvar o = 0; o < O; o++) begin : g_output_map
                assign output_links[(n*O+o)*LX+:LX] = LX'(output_link(n, o));
                assign output_target[(n*O+o)*HW+:HW] = HW'(
                    output_link(n, o) < IL ? destination_resource(output_link(n, o)) : RES);
            end

            if (NODE_PRESENT_MASK[n] && CO > 0) begin : g_present
                wire [CO-1:0] enable;
                wire [CO*S-1:0] select_input;
                wire [CO-1:0] valid_output;
                wire [CO-1:0] ready_output;
                wire [CO*D-1:0] data_output;
                wire [CO*M-1:0] metadata_output;

                for (genvar o = 0; o < O; o++) begin : g_row
                    if (|NODE_CONNECTIVITY_MASKS[n*O*I+o*I+:I]) begin : g_connected
                        localparam int J = row_rank(n, o);
                        assign enable[J] = active_route[n*O+o];
                        assign select_input[J*S+:S] = active_route[N*O+(n*O+o)*S+:S];
                        assign raw_output_valid[n*O+o] = valid_output[J];
                        assign ready_output[J] = output_ready[n*O+o];
                        assign raw_output_data[(n*O+o)*D+:D] = data_output[J*D+:D];
                        assign raw_output_metadata[(n*O+o)*M+:M] = metadata_output[J*M+:M];
                    end else begin : g_absent
                        assign raw_output_valid[n*O+o] = 1'b0;
                        assign raw_output_data[(n*O+o)*D+:D] = '0;
                        assign raw_output_metadata[(n*O+o)*M+:M] = '0;
                    end
                end

                static_mesh_node #(
                    .I(I),
                    .O(CO),
                    .D(D),
                    .M(M),
                    .CI(CI),
                    .PROTECTION(CONTROL_PROTECTION),
                    .MULTICAST(SUPPORT_MULTICAST),
                    .ASYNC_RESET(ASYNC_RESET),
                    .MATRIX((CO*I)'(compact_matrix(n)))
                ) u_node (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all),
                    .i_error_clear(i_error_clear),
                    .i_install(install && (&node_ready)),
                    .i_route_check(route_check),
                    .i_enable(enable),
                    .i_select(select_input),
                    .i_context(install_context),
                    .o_install_ready(node_ready[n]),
                    .o_match(node_match[n]),
                    .i_valid(input_valid[n*I+:I]),
                    .o_ready(raw_input_ready[n*I+:I]),
                    .i_data(input_data[n*I*D+:I*D]),
                    .i_metadata(input_metadata[n*I*M+:I*M]),
                    .o_valid(valid_output),
                    .i_ready(ready_output),
                    .o_data(data_output),
                    .o_metadata(metadata_output),
                    .o_buffered(buffered[n*I+:I]),
                    .o_idle(node_idle[n]),
                    .o_bad(node_bad[n]),
                    .o_error(node_error[n]),
                    .o_multicast(multicast[n])
                );
            end else begin : g_absent
                assign raw_input_ready[n*I+:I] = '0;
                assign raw_output_valid[n*O+:O] = '0;
                assign raw_output_data[n*O*D+:O*D] = '0;
                assign raw_output_metadata[n*O*M+:O*M] = '0;
                assign buffered[n*I+:I] = '0;
                assign node_idle[n] = 1'b1;
                assign node_ready[n] = 1'b1;
                assign node_match[n] = 1'b1;
                assign node_bad[n] = 1'b0;
                assign node_error[n] = 1'b0;
                assign multicast[n] = 1'b0;
            end

            assign o_node_buffered[n*I+:I] = run &&!node_bad[n] ? buffered[n*I+:I] : '0;
            assign o_node_clock_enable[n] = run && NODE_PRESENT_MASK[n] &&
                (!node_idle[n] || (|input_valid[n*I+:I]) || configuration_busy ||
                i_drain === 1'b1 || i_flush === 1'b1 || i_test_enable === 1'b1 ||
                i_scan_enable === 1'b1 || schedule_check);

            for (genvar i = 0; i < TX; i++) begin : g_inject
                localparam int J = n * TX + i;
                wire valid_meta = legal_metadata(i_tile_tx_data[J*D+:D],
                    i_pred_tx_metadata[J*M+:M], PR'(J));
                assign raw_input_valid[n*I+i] = NODE_PRESENT_MASK[n] && ingress && valid_meta &&
                    i_pred_tx_valid[J] === 1'b1;
                assign raw_input_data[(n*I+i)*D+:D] = input_valid[n*I+i] ?
                    canonical(i_tile_tx_data[J*D+:D]) : '0;
                assign raw_input_metadata[(n*I+i)*M+:M] = input_valid[n*I+i] ?
                    i_pred_tx_metadata[J*M+:M] : '0;
                assign o_pred_tx_ready[J] = NODE_PRESENT_MASK[n] && ingress && valid_meta &&
                    (i_pred_tx_valid[J] === 1'b0 || i_pred_tx_valid[J] === 1'b1) &&
                    input_ready[n*I+i];
                assign metadata_bad[J] = NODE_PRESENT_MASK[n] && ingress &&
                    i_pred_tx_valid[J] === 1'b1 &&!valid_meta;
                assign injection_stall[J] = NODE_PRESENT_MASK[n] && run &&!flush_all &&
                    i_pred_tx_valid[J] === 1'b1 &&!o_pred_tx_ready[J];
            end

            for (genvar o = 0; o < RX; o++) begin : g_eject
                localparam int J = n * RX + o;
                assign o_pred_rx_valid[J] = transport && output_valid[n*O+o] &&
                    !quarantine[J] &&!alignment_event[J];
                assign o_tile_rx_data[J*D+:D] = o_pred_rx_valid[J] ?
                    output_data[(n*O+o)*D+:D] : '0;
                assign o_pred_rx_metadata[J*M+:M] = o_pred_rx_valid[J] ?
                    output_metadata[(n*O+o)*M+:M] : '0;
                assign raw_output_ready[n*O+o] = transport && i_tile_rx_ready[J] === 1'b1;
                assign ejection_stall[J] = o_pred_rx_valid[J] && i_tile_rx_ready[J] !== 1'b1;
            end

            for (genvar i = TX; i < I; i++) begin : g_missing_input
                localparam int LI = input_link(n, i);

                if (LI == L ||!LINK_PRESENT_MASK[LI]) begin : g_tie
                    assign raw_input_valid[n*I+i] = 1'b0;
                    assign raw_input_data[(n*I+i)*D+:D] = '0;
                    assign raw_input_metadata[(n*I+i)*M+:M] = '0;
                end
            end

            for (genvar o = RX; o < O; o++) begin : g_missing_output
                localparam int LI = output_link(n, o);

                if (LI == L ||!LINK_PRESENT_MASK[LI]) begin : g_tie
                    assign raw_output_ready[n*O+o] = 1'b0;
                end
            end
        end

        for (genvar l = 0; l < LB; l++) begin : g_link
            localparam int SRC = source_resource(l);
            localparam int DST = destination_resource(l);

            if (l < IL && LINK_PRESENT_MASK[l]) begin : g_internal
                wire [D+M-1:0] packet;

                static_mesh_link #(
                    .WIDTH(D + M),
                    .PARITY(ENABLE_LINK_PARITY),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_link (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all),
                    .i_run(transport),
                    .i_fault(o_faulted_link_mask[l]),
                    .i_valid(output_valid[SRC]),
                    .o_ready(raw_output_ready[SRC]),
                    .i_data({output_metadata[SRC*M+:M], output_data[SRC*D+:D]}),
                    .o_valid(raw_input_valid[DST]),
                    .i_ready(input_ready[DST]),
                    .o_data(packet),
                    .o_idle(link_idle[l]),
                    .o_transfer(link_transfer[l]),
                    .o_parity_bad(parity_bad[l]),
                    .o_bad(link_bad[l]),
                    .o_observed_data(observed[l])
                );

                assign raw_input_data[DST*D+:D] = packet[0+:D];
                assign raw_input_metadata[DST*M+:M] = packet[D+:M];
            end else if (l < IL || l >= L ||!LINK_PRESENT_MASK[l]) begin : g_absent
                assign observed[l] = '0;
                assign link_idle[l] = 1'b1;
                assign link_transfer[l] = 1'b0;
                assign parity_bad[l] = 1'b0;
                assign link_bad[l] = 1'b0;
            end else begin : g_boundary
                assign link_idle[l] = 1'b1;
                assign link_bad[l] = 1'b0;
            end
        end

        for (genvar b = 0; b < B; b++) begin : g_boundary
            localparam int IN = IL + 2 * b;
            localparam int OUT = IN + 1;
            localparam int SRC = source_resource(OUT);
            localparam int DST = destination_resource(IN);
            wire in_present = EXPOSE_BOUNDARY_PORTS && LINK_PRESENT_MASK[IN];
            wire out_present = EXPOSE_BOUNDARY_PORTS && LINK_PRESENT_MASK[OUT];
            wire qin_bad;
            wire qout_bad;

            if (EXPOSE_BOUNDARY_PORTS && LINK_PRESENT_MASK[IN]) begin : g_input
                wire ready;
                wire valid;
                wire [PKT-1:0] packet;
                wire [31:0] count;
                wire valid_meta = legal_metadata(i_boundary_rx_data[b*D+:D],
                    i_boundary_pred_metadata[b*M+:M], PR'(N * TX + b));
                wire input_parity_bad = ENABLE_LINK_PARITY && i_boundary_pred_valid[b] === 1'b1 &&
                    (^{i_boundary_pred_parity[b], canonical(i_boundary_rx_data[b*D+:D]),
                        i_boundary_pred_metadata[b*M+:M]} !== 1'b0);
                wire held_parity_bad = ENABLE_LINK_PARITY && valid && (^packet !== 1'b0);
                wire available = transport &&!o_faulted_link_mask[IN];

                static_mesh_queue #(
                    .WIDTH(PKT),
                    .DEPTH(BOUNDARY_BUFFER_DEPTH),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_queue (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all),
                    .i_valid(ingress && valid_meta &&!input_parity_bad && available &&
                        i_boundary_pred_valid[b] === 1'b1),
                    .o_ready(ready),
                    .i_data({ENABLE_LINK_PARITY ? i_boundary_pred_parity[b] : 1'b0,
                        i_boundary_pred_metadata[b*M+:M], canonical(i_boundary_rx_data[b*D+:D])}),
                    .o_valid(valid),
                    .i_ready(available &&!held_parity_bad && input_ready[DST]),
                    .o_data(packet),
                    .o_count(count),
                    .o_bad(qin_bad)
                );

                assign o_boundary_pred_ready[b] = ingress && available && valid_meta &&
                    (i_boundary_pred_valid[b] === 1'b0 || i_boundary_pred_valid[b] === 1'b1) &&
                    !input_parity_bad && ready;
                assign raw_input_valid[DST] = available && valid &&!held_parity_bad;
                assign raw_input_data[DST*D+:D] = input_valid[DST] ? packet[0+:D] : '0;
                assign raw_input_metadata[DST*M+:M] = input_valid[DST] ? packet[D+:M] : '0;
                assign boundary_idle[b] = count == 0;
                assign link_transfer[IN] = i_boundary_pred_valid[b] === 1'b1 &&
                    o_boundary_pred_ready[b];
                // An ingress parity failure has not entered the queue. Attribute
                // that failure to the offered token, rather than stale storage.
                assign observed[IN] = ingress && input_parity_bad ?
                    {i_boundary_pred_metadata[b*M+:M],
                        canonical(i_boundary_rx_data[b*D+:D])} : packet[0+:D+M];
                assign parity_bad[IN] = run &&!flush_all &&
                    ((ingress && input_parity_bad) || held_parity_bad);
                assign metadata_bad[N*TX+b] = ingress && i_boundary_pred_valid[b] === 1'b1 &&
                    !valid_meta;
            end else begin : g_no_input
                assign o_boundary_pred_ready[b] = 1'b0;
                assign boundary_idle[b] = 1'b1;
                assign qin_bad = 1'b0;
                assign metadata_bad[N*TX+b] = 1'b0;
            end

            if (EXPOSE_BOUNDARY_PORTS && LINK_PRESENT_MASK[OUT]) begin : g_output
                wire ready;
                wire valid;
                wire [PKT-1:0] packet;
                wire [31:0] count;
                wire available = transport &&!o_boundary_isolated &&!o_faulted_link_mask[OUT];
                wire held_parity_bad = ENABLE_LINK_PARITY && valid && (^packet !== 1'b0);
                wire [D+M-1:0] payload =
                    {output_metadata[SRC*M+:M], output_data[SRC*D+:D]};

                static_mesh_queue #(
                    .WIDTH(PKT),
                    .DEPTH(BOUNDARY_BUFFER_DEPTH),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_queue (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all),
                    .i_valid(available && output_valid[SRC]),
                    .o_ready(ready),
                    .i_data({ENABLE_LINK_PARITY ? ^payload : 1'b0, payload}),
                    .o_valid(valid),
                    .i_ready(available &&!held_parity_bad &&
                        i_boundary_pred_ready[b] === 1'b1),
                    .o_data(packet),
                    .o_count(count),
                    .o_bad(qout_bad)
                );

                assign raw_output_ready[SRC] = available && ready;
                assign o_boundary_pred_valid[b] = available && valid &&!held_parity_bad;
                assign o_boundary_tx_data[b*D+:D] = o_boundary_pred_valid[b] ? packet[0+:D] : '0;
                assign o_boundary_pred_metadata[b*M+:M] =
                    o_boundary_pred_valid[b] ? packet[D+:M] : '0;
                assign o_boundary_pred_parity[b] = o_boundary_pred_valid[b] ? packet[D+M] : 1'b0;
                assign boundary_idle[B+b] = count == 0;
                assign link_transfer[OUT] = o_boundary_pred_valid[b] &&
                    i_boundary_pred_ready[b] === 1'b1;
                assign observed[OUT] = packet[0+:D+M];
                assign parity_bad[OUT] = run &&!flush_all && held_parity_bad;
            end else begin : g_no_output
                assign o_boundary_pred_valid[b] = 1'b0;
                assign o_boundary_tx_data[b*D+:D] = '0;
                assign o_boundary_pred_metadata[b*M+:M] = '0;
                assign o_boundary_pred_parity[b] = 1'b0;
                assign boundary_idle[B+b] = 1'b1;
                assign qout_bad = 1'b0;
            end

            assign boundary_bad[b] = qin_bad || qout_bad;
            assign boundary_stall[b] = run && in_present &&!flush_all &&
                i_boundary_pred_valid[b] === 1'b1 &&!o_boundary_pred_ready[b];
            assign boundary_stall[B+b] = o_boundary_pred_valid[b] &&
                i_boundary_pred_ready[b] !== 1'b1;
        end

        wire [RES*PM-1:0] input_slots;
        wire [RES-1:0] checked_inputs;

        predicate_network_schedule #(
            .N(N),
            .I(I),
            .O(O),
            .TX(TX),
            .RX(RX),
            .IL(IL),
            .L(L),
            .LB(LB),
            .LX(LX),
            .PM(PM),
            .PW(PW),
            .S(S),
            .RI(RI)
        ) u_schedule (
            .i_route(active_route),
            .i_enable(schedule_enable),
            .i_slots(slots),
            .i_period(period),
            .i_inputs(input_links),
            .i_outputs(output_links),
            .o_input_slots(input_slots),
            .o_checked(checked_inputs),
            .o_bad()
        );

        function automatic int resource_link(input int u);
            int link_id;
            link_id = input_link(u / I, u % I);

            if (link_id < L) return link_id;

            for (int o = 0; o < O; o++)
                if (active_route[u/I*O+o] &&
                    active_route[N*O+(u/I*O+o)*S+:S] == S'(u % I) && output_link(u/I, o) < L)

                    return output_link(u/I, o);

            return 0;

        endfunction

        // Slots diagnose rather than retime traffic. A violation never changes
        // pending branch ownership or labels a delayed token as a new token.
        always @* begin
            int phase;
            phase = period > 0 ? int'(tick % 32'(period)) : 0;
            schedule_violation = '0;

            if (schedule_check && period > 0) begin
                for (int u = 0; u < RES; u++) begin
                    int link_id;
                    int startup;
                    link_id = resource_link(u);
                    startup = int'(depths[u*HW+:HW]);

                    if (checked_inputs[u] && tick >= 32'(startup)) begin
                        if (input_valid[u] && (!input_slots[u*PM+phase] || !input_ready[u]))
                            schedule_violation[link_id] = 1'b1;

                        if (i_drain === 1'b0 && input_slots[u*PM+phase] && !input_valid[u])
                            schedule_violation[link_id] = 1'b1;
                    end
                end

                for (int node = 0; node < N; node++) begin
                    for (int o = 0; o < RX; o++) begin
                        int source;
                        int u;
                        int previous;
                        source = int'(active_route[N*O+(node*O+o)*S+:S]);
                        u = node * I + (source < I ? source : 0);
                        previous = (phase + int'(period) - 1) % int'(period);

                        if (active_route[node*O+o] && checked_inputs[u] &&
                            tick >= 32'(depths[u*HW+:HW]) + 1) begin

                            if (output_valid[node*O+o] &&
                                (!input_slots[u*PM+previous] || !output_ready[node*O+o]))
                                schedule_violation[resource_link(u)] = 1'b1;

                            if (i_drain === 1'b0 && input_slots[u*PM+previous] &&
                                !output_valid[node*O+o])
                                schedule_violation[resource_link(u)] = 1'b1;
                        end
                    end
                end

                for (int b = 0; b < B; b++) begin
                    if (EXPOSE_BOUNDARY_PORTS) begin
                        int incoming;
                        int outgoing;
                        incoming = IL + 2 * b;
                        outgoing = incoming + 1;

                        if (schedule_enable[incoming]) begin
                            if (i_boundary_pred_valid[b] === 1'b1 &&
                                (!slots[incoming*PM+phase] || !o_boundary_pred_ready[b]))
                                schedule_violation[incoming] = 1'b1;

                            if (i_drain === 1'b0 && slots[incoming*PM+phase] &&
                                i_boundary_pred_valid[b] !== 1'b1)
                                schedule_violation[incoming] = 1'b1;
                        end

                        if (schedule_enable[outgoing] &&
                            tick >= 32'(depths[(source_resource(outgoing)/O*I+
                                int'(active_route[N*O+source_resource(outgoing)*S+:S]))*HW+:HW])+2)
                            if ((o_boundary_pred_valid[b] && (!slots[outgoing*PM+phase] ||
                                i_boundary_pred_ready[b] !== 1'b1)) ||
                                (i_drain === 1'b0 && slots[outgoing*PM+phase] &&
                                !o_boundary_pred_valid[b])) schedule_violation[outgoing] = 1'b1;
                    end
                end
            end
        end

        // First-error attribution includes producer, tag, context and epoch.
        // Alignment reports quarantine the affected output before any handshake.
        always @* begin
            runtime_code = PRED_NET_OK;
            runtime_node = '0;
            runtime_link = '0;
            runtime_source = '0;
            runtime_tag = '0;
            runtime_expected_tag = '0;

            if (|counter_overflow) runtime_code = PRED_NET_ERR_COUNTER;

            if (|node_error) runtime_code = PRED_NET_ERR_UNKNOWN;

            if (schedule_check && i_schedule_pause === 1'b1 &&
                (!all_idle || (period != 0 && tick % 32'(period) != 0)))
                runtime_code = PRED_NET_ERR_SCHEDULE;

            for (int l = L - 1; l >= 0; l--) begin
                if (schedule_violation[l]) begin
                    runtime_code = PRED_NET_ERR_SCHEDULE;
                    runtime_link = LI'(l);
                end

                if (parity_bad[l]) begin
                    runtime_code = PRED_NET_ERR_PARITY;
                    runtime_link = LI'(l);
                    runtime_node = NI'(l >= IL && (l - IL) % 2 == 1 ?
                        source_resource(l) / O : destination_resource(l) / I);
                    runtime_source = (^observed[l][D+CI+V+K+EP+:PR] !== 1'bx) ?
                        observed[l][D+CI+V+K+EP+:PR] : '0;
                    runtime_tag = (^observed[l][D+CI+V+K+EP+PR+:T] !== 1'bx) ?
                        observed[l][D+CI+V+K+EP+PR+:T] : '0;
                end
            end

            for (int j = N * TX - 1; j >= 0; j--) begin
                if (metadata_bad[j]) begin
                    runtime_code = token_error(i_tile_tx_data[j*D+:D],
                        i_pred_tx_metadata[j*M+:M], PR'(j));
                    runtime_node = NI'(j / TX);
                    runtime_source = PR'(j);
                    runtime_tag = (^i_pred_tx_metadata[j*M+CI+V+K+EP+PR+:T] !== 1'bx) ?
                        i_pred_tx_metadata[j*M+CI+V+K+EP+PR+:T] : '0;
                end

                if (ingress && i_pred_tx_valid[j] !== 1'b0 && i_pred_tx_valid[j] !== 1'b1)
                    runtime_code = PRED_NET_ERR_UNKNOWN;
            end

            for (int b = B - 1; b >= 0; b--) begin
                if (metadata_bad[N*TX+b]) begin
                    runtime_code = token_error(i_boundary_rx_data[b*D+:D],
                        i_boundary_pred_metadata[b*M+:M], PR'(N * TX + b));
                    runtime_node = NI'(destination_resource(IL + 2 * b) / I);
                    runtime_link = LI'(IL + 2 * b);
                    runtime_source = PR'(N * TX + b);
                    runtime_tag = (^i_boundary_pred_metadata[b*M+CI+V+K+EP+PR+:T] !== 1'bx) ?
                        i_boundary_pred_metadata[b*M+CI+V+K+EP+PR+:T] : '0;
                end

                if (EXPOSE_BOUNDARY_PORTS && ingress &&
                    LINK_PRESENT_MASK[IL+2*b] && i_boundary_pred_valid[b] !== 1'b0 &&
                    i_boundary_pred_valid[b] !== 1'b1) runtime_code = PRED_NET_ERR_UNKNOWN;

                if (o_boundary_pred_valid[b] && i_boundary_pred_ready[b] !== 1'b0 &&
                    i_boundary_pred_ready[b] !== 1'b1) runtime_code = PRED_NET_ERR_UNKNOWN;
            end

            for (int j = N * RX - 1; j >= 0; j--) begin
                if (o_pred_rx_valid[j] && i_pred_rx_ready[j] !== 1'b0 &&
                    i_pred_rx_ready[j] !== 1'b1) begin
                    runtime_code = PRED_NET_ERR_UNKNOWN;
                    runtime_node = NI'(j / RX);
                end

                if (alignment_event[j]) begin
                    runtime_code = PRED_NET_ERR_ALIGNMENT;
                    runtime_node = NI'(j / RX);
                    runtime_source = output_metadata[(j/RX*O+j%RX)*M+CI+V+K+EP+:PR];
                    runtime_tag = (^observed_tags[j*T+:T] !== 1'bx) ? observed_tags[j*T+:T] : '0;
                    runtime_expected_tag = (^expected_tags[j*T+:T] !== 1'bx) ?
                        expected_tags[j*T+:T] : '0;
                end
            end
        end

        banked_scratchpad_state #(
            .WIDTH(LB),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_parity_seen (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_data(next_parity_seen),
            .o_data(parity_seen),
            .o_bad(parity_seen_bad)
        );

        dff #(
            .WIDTH(3 * LB + N * (TX + 2 * RX + 1)),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_events (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d({link_transfer, parity_pulse, schedule_violation, injection_stall,
                ejection_stall, multicast, alignment_event}),
            .o_q({o_link_transfer, o_parity_error_event, o_schedule_violation,
                o_injection_stall, o_ejection_stall, o_multicast_event, o_alignment_error_event})
        );

        localparam int TX_BASE = 32;
        localparam int RX_BASE = TX_BASE + 4 * N * TX;
        localparam int LINK_BASE = RX_BASE + 4 * N * RX;
        localparam int NODE_BASE = LINK_BASE + 4 * LB;
        localparam int ALIGN_BASE = NODE_BASE + 4 * N;
        logic [COUNTERS*32-1:0] increments;
        wire [31:0] values [COUNTERS];
        wire [N*32+32-1:0] peaks;
        logic [N*32+32-1:0] peaks_next;
        logic [31:0] read_value;
        wire [32:0] counter_read;

        always @* begin
            int occupancy;
            int total;
            increments = '0;
            peaks_next = peaks;
            total = 0;
            increments[0*32+:32] = 32'($countones(i_pred_tx_valid));
            increments[1*32+:32] = 32'($countones(i_pred_tx_valid & o_pred_tx_ready));
            increments[2*32+:32] = 32'($countones(o_pred_rx_valid & i_pred_rx_ready));
            increments[3*32+:32] = 32'($countones(link_transfer));
            increments[4*32+:32] = 32'($countones(multicast));
            increments[5*32+:32] = 32'($countones(alignment_event));
            increments[6*32+:32] = 32'($countones(parity_pulse));
            increments[7*32+:32] = 32'($countones(schedule_violation));
            increments[8*32+:32] = 32'(o_cfg_committed);
            increments[9*32+:32] = 32'(o_cfg_aborted);
            increments[10*32+:32] = 32'(o_cfg_prepared);
            increments[11*32+:32] = 32'(o_cfg_prepare_rejected);
            increments[12*32+:32] = 32'(i_drain === 1'b1);
            increments[13*32+:32] = 32'(i_flush === 1'b1);
            increments[14*32+:32] = 32'(o_active_link_fault);
            increments[15*32+:32] = 32'(o_idle);
            increments[16*32+:32] = 32'($countones(injection_stall));
            increments[17*32+:32] = 32'($countones(ejection_stall));
            increments[18*32+:32] = 32'($countones(boundary_stall));
            increments[19*32+:32] = 32'($countones(metadata_bad));
            increments[20*32+:32] = 32'(configuration_busy);

            for (int j = 0; j < N * TX; j++) begin
                increments[(TX_BASE+4*j)*32+:32] = 32'(i_pred_tx_valid[j] === 1'b1);

                if (i_pred_tx_valid[j] === 1'b1 && o_pred_tx_ready[j]) begin
                    increments[(TX_BASE+4*j+1)*32+:32] = 1;
                    increments[(TX_BASE+4*j+2)*32+:32] =
                        32'($countones(i_pred_tx_lane_valid[j*PV+:PV]));
                    increments[(TX_BASE+4*j+3)*32+:32] =
                        32'($countones(i_pred_tx_value[j*PV+:PV] & i_pred_tx_lane_valid[j*PV+:PV]));
                end
            end

            for (int j = 0; j < N * RX; j++) begin
                increments[(RX_BASE+4*j)*32+:32] = 32'(o_pred_rx_valid[j]);

                if (o_pred_rx_valid[j] && i_pred_rx_ready[j] === 1'b1) begin
                    increments[(RX_BASE+4*j+1)*32+:32] = 1;
                    increments[(RX_BASE+4*j+2)*32+:32] =
                        32'($countones(o_pred_rx_lane_valid[j*PV+:PV]));
                    increments[(RX_BASE+4*j+3)*32+:32] =
                        32'($countones(o_pred_rx_value[j*PV+:PV]));
                end

                increments[(ALIGN_BASE+j)*32+:32] = 32'(alignment_event[j]);
            end

            for (int l = 0; l < LB; l++) begin
                increments[(LINK_BASE+4*l)*32+:32] = 32'(link_transfer[l]);
                increments[(LINK_BASE+4*l+1)*32+:32] = 32'(!link_idle[l]);
                increments[(LINK_BASE+4*l+2)*32+:32] = 32'(parity_pulse[l]);
                increments[(LINK_BASE+4*l+3)*32+:32] = 32'(schedule_violation[l]);
            end

            for (int node = 0; node < N; node++) begin
                occupancy = $countones(o_node_buffered[node*I+:I]);
                total += occupancy;
                increments[(NODE_BASE+4*node)*32+:32] = 32'(occupancy);
                increments[(NODE_BASE+4*node+1)*32+:32] = 32'(node_idle[node]);
                increments[(NODE_BASE+4*node+2)*32+:32] = 32'(!o_node_clock_enable[node]);
                increments[(NODE_BASE+4*node+3)*32+:32] = 32'(multicast[node]);

                if (32'(occupancy) > peaks[node*32+:32])
                    peaks_next[node*32+:32] = 32'(occupancy);
            end

            if (32'(total) > peaks[N*32+:32]) peaks_next[N*32+:32] = 32'(total);

            read_value = '0;

            if (int'(i_counter_index) < COUNTERS) read_value = values[i_counter_index];
            else if (int'(i_counter_index) <= COUNTERS + N)
                read_value = peaks[(int'(i_counter_index)-COUNTERS)*32+:32];
        end

        for (genvar c = 0; c < COUNTERS; c++) begin : g_count
            wire [32:0] sum = {1'b0, values[c]} + {1'b0, increments[c*32+:32]};

            banked_scratchpad_counters #(
                .COUNT(1),
                .PEAKS(1),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_count (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_increments(increments[c*32+:32]),
                .i_occupancy(32'b0),
                .o_counts(values[c]),
                .o_peaks()
            );

            assign counter_overflow[c] = run && sum[32];
        end

        dff #(.WIDTH((N + 1) * 32), .ASYNC_RESET(ASYNC_RESET)) u_peaks (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d(peaks_next),
            .o_q(peaks)
        );

        dff #(.WIDTH(33), .ASYNC_RESET(ASYNC_RESET)) u_count_read (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d({i_counter_read === 1'b1 && (^i_counter_index !== 1'bx) &&
                int'(i_counter_index) <= COUNTERS + N, read_value}),
            .o_q(counter_read)
        );

        assign o_counter_valid = run && counter_read[32];
        assign o_counter_value = o_counter_valid ? counter_read[0+:32] : '0;
    end
endmodule
`default_nettype wire
