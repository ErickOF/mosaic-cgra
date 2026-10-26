`timescale 1ns / 1ps
`default_nettype none

module static_mesh #(
    parameter MESH_ROWS = 4,
    parameter MESH_COLS = 4,
    parameter CHANNELS_PER_DIRECTION = 1,
    parameter LOCAL_TX_PORTS = 2,
    parameter LOCAL_RX_PORTS = 2,
    parameter LINK_DATA_WIDTH = 32,
    parameter LINK_METADATA_WIDTH = 64,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter CONTEXT_CHECKSUM_WIDTH = 32,
    parameter KERNEL_ID_WIDTH = 16,
    parameter LINK_EPOCH_WIDTH = 2,
    parameter ROUTE_PROOF_ID_WIDTH = 32,
    parameter CONNECTIVITY_PROFILE = 1,
    parameter EXPOSE_BOUNDARY_PORTS = 1,
    parameter SUPPORT_MULTICAST = 1,
    parameter MAX_MULTICAST_FANOUT = 4,
    parameter FLOW_PROFILE = 0,
    parameter BOUNDARY_BUFFER_DEPTH = 1,
    parameter MAX_COMBINATIONAL_HOPS = 0,
    parameter MAX_READY_COMBINATIONAL_NODES = 1,
    parameter SCHEDULE_PERIOD_MAX = 256,
    parameter CHECK_CONTEXT = 1,
    parameter ENABLE_LINK_PARITY = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter SUPPORT_LINK_EXCLUSION = 1,
    parameter ASYNC_RESET = 0,
    localparam int R = MESH_ROWS > 0 && MESH_ROWS <= 8 && (^MESH_ROWS !== 1'bx) ? MESH_ROWS : 1,
    localparam int C = MESH_COLS > 0 && MESH_COLS <= 8 && (^MESH_COLS !== 1'bx) ? MESH_COLS : 1,
    localparam int H = CHANNELS_PER_DIRECTION > 0 && CHANNELS_PER_DIRECTION <= 4 &&
        (^CHANNELS_PER_DIRECTION !== 1'bx) ? CHANNELS_PER_DIRECTION : 1,
    localparam int TX = LOCAL_TX_PORTS > 0 && LOCAL_TX_PORTS <= 8 &&
        (^LOCAL_TX_PORTS !== 1'bx) ? LOCAL_TX_PORTS : 1,
    localparam int RX = LOCAL_RX_PORTS > 0 && LOCAL_RX_PORTS <= 8 &&
        (^LOCAL_RX_PORTS !== 1'bx) ? LOCAL_RX_PORTS : 1,
    localparam int N = R * C,
    localparam int I = TX + 4 * H,
    localparam int O = RX + 4 * H,
    localparam int D = LINK_DATA_WIDTH >= 16 && LINK_DATA_WIDTH <= 128 &&
        (^LINK_DATA_WIDTH !== 1'bx) ? LINK_DATA_WIDTH : 16,
    localparam int M = LINK_METADATA_WIDTH >= 8 && LINK_METADATA_WIDTH <= 512 &&
        (^LINK_METADATA_WIDTH !== 1'bx) ? LINK_METADATA_WIDTH : 64,
    localparam int CD = CONTEXT_DEPTH > 0 && CONTEXT_DEPTH <= 16 &&
        (^CONTEXT_DEPTH !== 1'bx) ? CONTEXT_DEPTH : 1,
    localparam int W = CONFIG_DATA_WIDTH >= 8 && CONFIG_DATA_WIDTH <= 256 &&
        (^CONFIG_DATA_WIDTH !== 1'bx) ? CONFIG_DATA_WIDTH : 8,
    localparam int CI = CONTEXT_ID_WIDTH > 0 && CONTEXT_ID_WIDTH <= 32 &&
        (^CONTEXT_ID_WIDTH !== 1'bx) ? CONTEXT_ID_WIDTH : 1,
    localparam int V = CONTEXT_VERSION_WIDTH > 0 && CONTEXT_VERSION_WIDTH <= 32 &&
        (^CONTEXT_VERSION_WIDTH !== 1'bx) ? CONTEXT_VERSION_WIDTH : 1,
    localparam int K = KERNEL_ID_WIDTH > 0 && KERNEL_ID_WIDTH <= 32 &&
        (^KERNEL_ID_WIDTH !== 1'bx) ? KERNEL_ID_WIDTH : 1,
    localparam int EP = LINK_EPOCH_WIDTH > 0 && LINK_EPOCH_WIDTH <= 32 &&
        (^LINK_EPOCH_WIDTH !== 1'bx) ? LINK_EPOCH_WIDTH : 1,
    localparam int P = ROUTE_PROOF_ID_WIDTH >= 32 && ROUTE_PROOF_ID_WIDTH <= 64 &&
        (^ROUTE_PROOF_ID_WIDTH !== 1'bx) ? ROUTE_PROOF_ID_WIDTH : 32,
    localparam int PM = SCHEDULE_PERIOD_MAX > 0 && SCHEDULE_PERIOD_MAX <= 256 &&
        (^SCHEDULE_PERIOD_MAX !== 1'bx) ? SCHEDULE_PERIOD_MAX : 1,
    localparam int B = 2 * H * (R + C),
    localparam int IL = 2 * H * (R * (C - 1) + (R - 1) * C),
    localparam int L = IL + (EXPOSE_BOUNDARY_PORTS === 1 ? 2 * B : 0),
    localparam int LB = L > 0 ? L : 1,
    localparam int LI = L > 1 ? $clog2(L) : 1,
    localparam int LX = $clog2(LB + 1),
    localparam int NI = N > 1 ? $clog2(N) : 1,
    localparam int S = $clog2(I),
    localparam int OS = $clog2(O),
    localparam int RW = $clog2(N * I),
    localparam int AW = $clog2((N * I + 1) * (PM + 1) + 4),
    localparam int PW = $clog2(PM + 1),
    localparam int HEADER = 8 + 32 + V + K + P + PW + 1,
    localparam int IMAGE = HEADER + N * O * (1 + S) + N * I * (RW + AW),
    localparam int WORDS = (IMAGE + W - 1) / W,
    localparam int IM = WORDS * W,
    localparam int WI = WORDS > 1 ? $clog2(WORDS) : 1,
    localparam int COUNTERS = 16 + 2 * N * (TX + RX) + 3 * LB + 4 * B + 4 * N,
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
    input wire i_cfg_valid,
    input wire i_cfg_rsp_ready,
    input wire i_link_fault_valid,
    input wire i_counter_read,
    input wire i_boundary_isolate,
    input wire i_test_enable,
    input wire i_scan_enable,
    output wire o_idle,
    output wire o_quiescent,
    output wire o_drained,
    output wire o_flush_completed,
    output wire o_cfg_ready,
    output wire o_cfg_rsp_valid,
    output wire o_cfg_rsp_error,
    output wire o_active_context_valid,
    output wire o_active_link_fault,
    output wire o_link_fault_ready,
    output wire o_error,
    output wire o_counter_valid,
    output wire o_boundary_isolated,
    input wire [N*TX-1:0] i_tile_tx_valid,
    input wire [N*TX*D-1:0] i_tile_tx_data,
    input wire [N*TX*M-1:0] i_tile_tx_metadata,
    output wire [N*RX-1:0] o_tile_rx_valid,
    output wire [N*RX*D-1:0] o_tile_rx_data,
    output wire [N*RX*M-1:0] o_tile_rx_metadata,
    output wire [N*TX-1:0] o_tile_tx_ready,
    input wire [N*RX-1:0] i_tile_rx_ready,
    input wire [B-1:0] i_boundary_rx_valid,
    input wire [B*D-1:0] i_boundary_rx_data,
    input wire [B*M-1:0] i_boundary_rx_metadata,
    input wire [B-1:0] i_boundary_rx_parity,
    output wire [B-1:0] o_boundary_tx_valid,
    output wire [B*D-1:0] o_boundary_tx_data,
    output wire [B*M-1:0] o_boundary_tx_metadata,
    output wire [B-1:0] o_boundary_tx_parity,
    output wire [B-1:0] o_boundary_rx_ready,
    input wire [B-1:0] i_boundary_tx_ready,
    input wire [2:0] i_cfg_opcode,
    input wire [CI-1:0] i_cfg_context_id,
    input wire [V-1:0] i_cfg_context_version,
    input wire [WI-1:0] i_cfg_word_index,
    input wire [W-1:0] i_cfg_write_data,
    input wire [W/8-1:0] i_cfg_write_strobe,
    input wire [K-1:0] i_cfg_kernel_id,
    input wire [P-1:0] i_cfg_proof_id,
    input wire [31:0] i_cfg_checksum,
    output wire [CI-1:0] o_cfg_rsp_context_id,
    output wire [V-1:0] o_cfg_rsp_context_version,
    output wire [W-1:0] o_cfg_rsp_read_data,
    output wire [31:0] o_cfg_rsp_checksum,
    output wire [7:0] o_cfg_rsp_error_code,
    output wire [CI-1:0] o_active_context_id,
    output wire [V-1:0] o_active_context_version,
    output wire [K-1:0] o_active_kernel_id,
    output wire [EP-1:0] o_active_epoch,
    output wire [CD-1:0] o_context_valid,
    input wire [LB-1:0] i_link_fault_mask,
    output wire [LB-1:0] o_faulted_link_mask,
    output wire [LB-1:0] o_directed_link_active,
    output wire [LB-1:0] o_parity_error_event,
    output wire [N*I-1:0] o_node_buffered,
    output wire [N*TX-1:0] o_tile_injection_stall,
    output wire [N*RX-1:0] o_tile_ejection_stall,
    output wire [2*B-1:0] o_boundary_stall,
    output wire [N-1:0] o_multicast_event,
    output wire [N-1:0] o_schedule_violation,
    output wire [N-1:0] o_node_clock_enable,
    output wire [7:0] o_error_code,
    output wire [NI-1:0] o_error_node,
    output wire [LI-1:0] o_error_link,
    output wire [31:0] o_topology_id,
    output wire [31:0] o_counter_value,
    input wire [CW-1:0] i_counter_index
);
    import static_mesh_pkg::*;

    // Internal edges are horizontal (east, west), then vertical (south, north).
    // Channels increase inside each edge. Boundary input/output pairs follow.
    function automatic int internal_link(input int rows, input int cols, input int channels,
        input int node, input int direction, input int channel);

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

    function automatic int neighbor(input int rows, input int cols, input int node,
        input int direction);

        case (direction)
            0: return node / cols > 0 ? node - cols : -1;
            1: return node / cols + 1 < rows ? node + cols : -1;
            2: return node % cols + 1 < cols ? node + 1 : -1;
            3: return node % cols > 0 ? node - 1 : -1;
            default: return -1;
        endcase
    endfunction

    function automatic int boundary_port(input int rows, input int cols, input int channels,
        input int node, input int direction, input int channel);

        case (direction)
            0: return node / cols == 0 ? node % cols * channels + channel : -1;
            1: return node / cols == rows - 1 ? (cols + node % cols) * channels + channel : -1;
            3: return node % cols == 0 ? (2 * cols + node / cols) * channels + channel : -1;
            2: return node % cols == cols - 1 ?
                (2 * cols + rows + node / cols) * channels + channel : -1;
            default: return -1;
        endcase
    endfunction

    function automatic int output_link(input int node, input int output_port);
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

    function automatic int input_link(input int node, input int input_port);
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
                        (CONNECTIVITY_PROFILE >= 1 && outgoing != incoming) ||
                        CONNECTIVITY_PROFILE == 2)) result[node*O*I+o*I+i] = 1'b1;
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

    function automatic logic [31:0] topology_fingerprint();
        int n;
        int l;
        int b;
        logic [31:0] value;
        value = 32'h534d0101;
        value = (value ^ 32'(MESH_ROWS)) * 32'd16777619;
        value = (value ^ 32'(MESH_COLS)) * 32'd16777619;
        value = (value ^ 32'(CHANNELS_PER_DIRECTION)) * 32'd16777619;
        value = (value ^ 32'(LOCAL_TX_PORTS)) * 32'd16777619;
        value = (value ^ 32'(LOCAL_RX_PORTS)) * 32'd16777619;
        value = (value ^ 32'(LINK_DATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(LINK_METADATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(CONFIG_DATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_VERSION_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_CHECKSUM_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(KERNEL_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(LINK_EPOCH_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(ROUTE_PROOF_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONNECTIVITY_PROFILE)) * 32'd16777619;
        value = (value ^ 32'(EXPOSE_BOUNDARY_PORTS)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_MULTICAST)) * 32'd16777619;
        value = (value ^ 32'(MAX_MULTICAST_FANOUT)) * 32'd16777619;
        value = (value ^ 32'(FLOW_PROFILE)) * 32'd16777619;
        value = (value ^ 32'(BOUNDARY_BUFFER_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(MAX_COMBINATIONAL_HOPS)) * 32'd16777619;
        value = (value ^ 32'(MAX_READY_COMBINATIONAL_NODES)) * 32'd16777619;
        value = (value ^ 32'(SCHEDULE_PERIOD_MAX)) * 32'd16777619;
        value = (value ^ 32'(CHECK_CONTEXT)) * 32'd16777619;
        value = (value ^ 32'(ENABLE_LINK_PARITY)) * 32'd16777619;
        value = (value ^ 32'(CONTROL_PROTECTION)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_LINK_EXCLUSION)) * 32'd16777619;
        value = (value ^ 32'(ASYNC_RESET)) * 32'd16777619;

        for (n = 0; n < N; n++)
            value = (value ^ 32'(NODE_PRESENT_MASK[n])) * 32'd16777619;

        for (l = 0; l < L; l++)
            value = (value ^ 32'(LINK_PRESENT_MASK[l])) * 32'd16777619;

        for (b = 0; b < N * O * I; b++)
            value = (value ^ 32'(NODE_CONNECTIVITY_MASKS[b])) * 32'd16777619;

        return value;
    endfunction

    localparam logic [31:0] TOPOLOGY_ID = topology_fingerprint();
    assign o_topology_id = TOPOLOGY_ID;

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

    function automatic int row_rank(input int node, input int port_index);
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

    localparam bit PARAMETERS_VALID =
        ((MESH_ROWS > 0) === 1'b1) && (^MESH_ROWS !== 1'bx) &&
        ((MESH_COLS > 0) === 1'b1) && (^MESH_COLS !== 1'bx) &&
        ((CHANNELS_PER_DIRECTION > 0) === 1'b1) && (^CHANNELS_PER_DIRECTION !== 1'bx) &&
        ((LOCAL_TX_PORTS > 0) === 1'b1) && (^LOCAL_TX_PORTS !== 1'bx) &&
        ((LOCAL_RX_PORTS > 0) === 1'b1) && (^LOCAL_RX_PORTS !== 1'bx) &&
        ((LINK_DATA_WIDTH > 0) === 1'b1) && (^LINK_DATA_WIDTH !== 1'bx) &&
        ((LINK_METADATA_WIDTH > 0) === 1'b1) && (^LINK_METADATA_WIDTH !== 1'bx) &&
        ((CONTEXT_DEPTH > 0) === 1'b1) && (^CONTEXT_DEPTH !== 1'bx) &&
        ((CONFIG_DATA_WIDTH > 0) === 1'b1) && (^CONFIG_DATA_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH > 0) === 1'b1) && (^CONTEXT_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_VERSION_WIDTH > 0) === 1'b1) && (^CONTEXT_VERSION_WIDTH !== 1'bx) &&
        ((CONTEXT_CHECKSUM_WIDTH > 0) === 1'b1) && (^CONTEXT_CHECKSUM_WIDTH !== 1'bx) &&
        ((KERNEL_ID_WIDTH > 0) === 1'b1) && (^KERNEL_ID_WIDTH !== 1'bx) &&
        ((LINK_EPOCH_WIDTH > 0) === 1'b1) && (^LINK_EPOCH_WIDTH !== 1'bx) &&
        ((ROUTE_PROOF_ID_WIDTH > 0) === 1'b1) && (^ROUTE_PROOF_ID_WIDTH !== 1'bx) &&
        ((MAX_MULTICAST_FANOUT > 0) === 1'b1) && (^MAX_MULTICAST_FANOUT !== 1'bx) &&
        ((MAX_READY_COMBINATIONAL_NODES > 0) === 1'b1) &&
        (^MAX_READY_COMBINATIONAL_NODES !== 1'bx) &&
        ((SCHEDULE_PERIOD_MAX > 0) === 1'b1) && (^SCHEDULE_PERIOD_MAX !== 1'bx) &&
        (EXPOSE_BOUNDARY_PORTS === 0 || EXPOSE_BOUNDARY_PORTS === 1) &&
        (SUPPORT_MULTICAST === 0 || SUPPORT_MULTICAST === 1) &&
        (CHECK_CONTEXT === 0 || CHECK_CONTEXT === 1) &&
        (ENABLE_LINK_PARITY === 0 || ENABLE_LINK_PARITY === 1) &&
        (SUPPORT_LINK_EXCLUSION === 0 || SUPPORT_LINK_EXCLUSION === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1) &&
        MESH_ROWS <= 8 && MESH_COLS <= 8 && CHANNELS_PER_DIRECTION <= 4 &&
        LOCAL_TX_PORTS <= 8 && LOCAL_RX_PORTS <= 8 && CONTEXT_DEPTH <= 16 &&
        LINK_DATA_WIDTH >= 16 && LINK_DATA_WIDTH <= 128 && LINK_DATA_WIDTH % 8 == 0 &&
        LINK_METADATA_WIDTH <= 512 && LINK_METADATA_WIDTH % 8 == 0 &&
        LINK_METADATA_WIDTH >= CI + V + K + EP + D / 8 + 8 &&
        CONFIG_DATA_WIDTH <= 256 && CONFIG_DATA_WIDTH % 8 == 0 &&
        CONTEXT_ID_WIDTH <= 32 && CONTEXT_VERSION_WIDTH <= 32 && KERNEL_ID_WIDTH <= 32 &&
        LINK_EPOCH_WIDTH <= 32 && ROUTE_PROOF_ID_WIDTH >= 32 && ROUTE_PROOF_ID_WIDTH <= 64 &&
        CONTEXT_CHECKSUM_WIDTH == 32 && SCHEDULE_PERIOD_MAX <= 256 &&
        (64'(CONTEXT_DEPTH) <= (64'd1 << CONTEXT_ID_WIDTH)) &&
        (CONNECTIVITY_PROFILE === 0 || CONNECTIVITY_PROFILE === 1 || CONNECTIVITY_PROFILE === 2) &&
        (FLOW_PROFILE === 0 || FLOW_PROFILE === 1) &&
        (CONTROL_PROTECTION === 0 || CONTROL_PROTECTION === 1 || CONTROL_PROTECTION === 2) &&
        BOUNDARY_BUFFER_DEPTH >= 0 && BOUNDARY_BUFFER_DEPTH <= 8 &&
        (^BOUNDARY_BUFFER_DEPTH !== 1'bx) &&
        (BOUNDARY_BUFFER_DEPTH != 0 || FLOW_PROFILE == 1) &&
        (MAX_COMBINATIONAL_HOPS === 0) &&
        MAX_MULTICAST_FANOUT <= O &&
        $bits(NODE_PRESENT_MASK) == N && (^NODE_PRESENT_MASK !== 1'bx) &&
        $bits(LINK_PRESENT_MASK) == LB && (^LINK_PRESENT_MASK !== 1'bx) &&
        $bits(NODE_CONNECTIVITY_MASKS) == N * O * I && (^NODE_CONNECTIVITY_MASKS !== 1'bx) &&
        topology_valid();

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        static_mesh_parameters_must_be_valid invalid_parameters ();
    end else begin : g_mesh
        localparam int PKT = D + M + 1;
        localparam int SELECT_BASE = HEADER + N * O;
        localparam int ARRIVAL_BASE = SELECT_BASE + N * O * S + N * I * RW;
        wire run = i_reset_n === 1'b1;
        wire ingress;
        wire transport;
        wire install;
        wire flush_all;
        wire route_check;
        wire configuration_busy;
        wire schedule_check;
        wire activation;
        wire [31:0] tick;
        wire [CI-1:0] install_context;
        wire [IM-1:0] active_image;
        wire [N*I*LX-1:0] input_links;
        wire [N*O*LX-1:0] output_links;
        wire [LB*RW-1:0] link_destination;
        wire [LB*(NI+OS)-1:0] link_source;
        wire [N*I-1:0] raw_input_valid;
        logic [N*I-1:0] input_valid;
        wire [N*I-1:0] raw_input_ready;
        logic [N*I-1:0] input_ready;
        wire [N*I-1:0] buffered;
        wire [N*I*D-1:0] raw_input_data;
        logic [N*I*D-1:0] input_data;
        wire [N*I*M-1:0] raw_input_metadata;
        logic [N*I*M-1:0] input_metadata;
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
        wire [B-1:0] boundary_bad;
        wire [2*B-1:0] boundary_idle;
        wire [N*TX+B-1:0] metadata_bad;
        wire [N*TX+B-1:0] metadata_epoch_bad;
        wire [2*B-1:0] boundary_stall;
        wire [N*TX-1:0] injection_stall;
        wire [N*RX-1:0] ejection_stall;
        wire [LB-1:0] parity_seen;
        wire [LB-1:0] parity_pulse = parity_bad & ~parity_seen;
        wire [LB-1:0] next_parity_seen = flush_all || i_error_clear === 1'b1 ?
            '0 : parity_seen | parity_bad;
        wire parity_seen_bad;
        wire integrity_bad = (|node_bad) || (|link_bad) || (|boundary_bad) ||
            parity_seen_bad;
        wire all_idle = (&node_idle) && (&link_idle) && (&boundary_idle);
        logic [7:0] runtime_code;
        logic [NI-1:0] runtime_node;
        logic [LI-1:0] runtime_link;
        logic [N-1:0] schedule_violation;
        wire [COUNTERS-1:0] counter_overflow;
        assign o_idle = run && all_idle &&!integrity_bad;

        // Canonical fields are checked once at admission. Forwarding preserves
        // every metadata bit, including reserved upper bits, without rewriting.
        function automatic logic legal_metadata(input logic [D-1:0] data,
            input logic [M-1:0] meta);
            int b;

            logic legal;
            logic [D/8-1:0] keep;
            legal = (^data !== 1'bx) && (^meta !== 1'bx);
            keep = meta[CI+V+K+EP+:D/8];

            if (CHECK_CONTEXT) begin
                legal &= meta[0+:CI] == o_active_context_id;
                legal &= meta[CI+:V] == o_active_context_version;
                legal &= meta[CI+V+:K] == o_active_kernel_id;
                legal &= meta[CI+V+K+:EP] == o_active_epoch;
            end

            legal &= meta[CI+V+K+EP+D/8+6+:2] <= 1;
            legal &= (|keep) || meta[CI+V+K+EP+D/8+4];
            for (b = 0; b < D / 8; b++)
                if (!keep[b] && data[b*8+:8] != 0) legal = 1'b0;

            return legal;
        endfunction

        function automatic logic due(input int arrival, input int period);
            return period > 0 && tick >= 32'(arrival) &&
                ((tick - 32'(arrival)) % 32'(period)) == 0;
        endfunction

        // Assemble each physical vector before distributing its slices. This
        // is a combinational identity, with one driver and no added node stage.
        // It also prevents simulator strength-concat fanout from growing with N.
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

        static_mesh_control #(
            .N(N),
            .I(I),
            .O(O),
            .TX(TX),
            .RX(RX),
            .H(H),
            .D(D),
            .M(M),
            .CD(CD),
            .W(W),
            .CI(CI),
            .V(V),
            .K(K),
            .EP(EP),
            .P(P),
            .PM(PM),
            .B(B),
            .IL(IL),
            .L(L),
            .LB(LB),
            .LI(LI),
            .LX(LX),
            .NI(NI),
            .S(S),
            .OS(OS),
            .RW(RW),
            .AW(AW),
            .PW(PW),
            .HEADER(HEADER),
            .IMAGE(IMAGE),
            .WORDS(WORDS),
            .IM(IM),
            .WI(WI),
            .COUNTERS(COUNTERS),
            .CW(CW),
            .FLOW_PROFILE(FLOW_PROFILE),
            .BOUNDARY_BUFFER_DEPTH(BOUNDARY_BUFFER_DEPTH),
            .CHECK_CONTEXT(CHECK_CONTEXT),
            .ENABLE_LINK_PARITY(ENABLE_LINK_PARITY),
            .CONTROL_PROTECTION(CONTROL_PROTECTION),
            .SUPPORT_LINK_EXCLUSION(SUPPORT_LINK_EXCLUSION),
            .SUPPORT_MULTICAST(SUPPORT_MULTICAST),
            .MAX_MULTICAST_FANOUT(MAX_MULTICAST_FANOUT),
            .ASYNC_RESET(ASYNC_RESET),
            .TOPOLOGY_ID(TOPOLOGY_ID)
        ) u_control (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_enable(i_enable),
            .i_drain(i_drain),
            .i_flush(i_flush),
            .i_error_clear(i_error_clear),
            .i_boundary_isolate(i_boundary_isolate),
            .i_test_enable(i_test_enable),
            .i_scan_enable(i_scan_enable),
            .i_cfg_valid(i_cfg_valid),
            .o_cfg_ready(o_cfg_ready),
            .i_cfg_opcode(i_cfg_opcode),
            .i_cfg_context_id(i_cfg_context_id),
            .i_cfg_context_version(i_cfg_context_version),
            .i_cfg_word_index(i_cfg_word_index),
            .i_cfg_write_data(i_cfg_write_data),
            .i_cfg_write_strobe(i_cfg_write_strobe),
            .i_cfg_kernel_id(i_cfg_kernel_id),
            .i_cfg_proof_id(i_cfg_proof_id),
            .i_cfg_checksum(i_cfg_checksum),
            .o_cfg_rsp_valid(o_cfg_rsp_valid),
            .i_cfg_rsp_ready(i_cfg_rsp_ready),
            .o_cfg_rsp_context_id(o_cfg_rsp_context_id),
            .o_cfg_rsp_context_version(o_cfg_rsp_context_version),
            .o_cfg_rsp_read_data(o_cfg_rsp_read_data),
            .o_cfg_rsp_checksum(o_cfg_rsp_checksum),
            .o_cfg_rsp_error(o_cfg_rsp_error),
            .o_cfg_rsp_error_code(o_cfg_rsp_error_code),
            .o_active_context_valid(o_active_context_valid),
            .o_active_context_id(o_active_context_id),
            .o_active_context_version(o_active_context_version),
            .o_active_kernel_id(o_active_kernel_id),
            .o_active_epoch(o_active_epoch),
            .o_context_valid(o_context_valid),
            .i_link_fault_valid(i_link_fault_valid),
            .o_link_fault_ready(o_link_fault_ready),
            .i_link_fault_mask(i_link_fault_mask),
            .o_faulted_link_mask(o_faulted_link_mask),
            .o_active_link_fault(o_active_link_fault),
            .o_error(o_error),
            .o_error_code(o_error_code),
            .o_error_node(o_error_node),
            .o_error_link(o_error_link),
            .o_quiescent(o_quiescent),
            .o_drained(o_drained),
            .o_flush_completed(o_flush_completed),
            .o_boundary_isolated(o_boundary_isolated),
            .i_all_idle(all_idle),
            .i_nodes_ready(&node_ready),
            .i_nodes_match(&node_match),
            .i_integrity_bad(integrity_bad),
            .i_runtime_code(runtime_code),
            .i_runtime_node(runtime_node),
            .i_runtime_link(runtime_link),
            .i_connectivity(NODE_CONNECTIVITY_MASKS),
            .i_node_present(NODE_PRESENT_MASK),
            .i_link_present(LINK_PRESENT_MASK),
            .i_input_links(input_links),
            .i_output_links(output_links),
            .i_link_destination(link_destination),
            .i_link_source(link_source),
            .o_active_image(active_image),
            .o_ingress_permitted(ingress),
            .o_transport_permitted(transport),
            .o_install_valid(install),
            .o_flush_all(flush_all),
            .o_schedule_tick(tick),
            .o_schedule_check(schedule_check),
            .o_activation_event(activation),
            .o_configuration_busy(configuration_busy),
            .o_install_context(install_context),
            .o_route_check(route_check)
        );

        for (genvar n = 0; n < N; n++) begin : g_node
            localparam int CO = row_count(n);

            for (genvar i = 0; i < I; i++) begin : g_input_map
                assign input_links[(n*I+i)*LX+:LX] = LX'(input_link(n, i));
            end

            for (genvar o = 0; o < O; o++) begin : g_output_map
                assign output_links[(n*O+o)*LX+:LX] = LX'(output_link(n, o));
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
                        assign enable[J] = active_image[HEADER+n*O+o];
                        assign select_input[J*S+:S] = active_image[SELECT_BASE+(n*O+o)*S+:S];
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
                    i_tile_tx_metadata[J*M+:M]);
                assign raw_input_valid[n*I+i] = NODE_PRESENT_MASK[n] && ingress && valid_meta &&
                    i_tile_tx_valid[J] === 1'b1;
                assign raw_input_data[(n*I+i)*D+:D] = input_valid[n*I+i] ?
                    i_tile_tx_data[J*D+:D] : '0;
                assign raw_input_metadata[(n*I+i)*M+:M] = input_valid[n*I+i] ?
                    i_tile_tx_metadata[J*M+:M] : '0;
                assign o_tile_tx_ready[J] = NODE_PRESENT_MASK[n] && ingress && valid_meta &&
                    input_ready[n*I+i];
                assign metadata_bad[J] = NODE_PRESENT_MASK[n] && ingress &&
                    i_tile_tx_valid[J] === 1'b1 &&!valid_meta;
                assign metadata_epoch_bad[J] = metadata_bad[J] && CHECK_CONTEXT &&
                    i_tile_tx_metadata[J*M+CI+V+K+:EP] !== o_active_epoch;
                assign injection_stall[J] = NODE_PRESENT_MASK[n] && run &&!flush_all &&
                    i_tile_tx_valid[J] === 1'b1 &&!o_tile_tx_ready[J];
            end

            for (genvar o = 0; o < RX; o++) begin : g_eject
                localparam int J = n * RX + o;
                assign o_tile_rx_valid[J] = transport && output_valid[n*O+o];
                assign o_tile_rx_data[J*D+:D] = o_tile_rx_valid[J] ?
                    output_data[(n*O+o)*D+:D] : '0;
                assign o_tile_rx_metadata[J*M+:M] = o_tile_rx_valid[J] ?
                    output_metadata[(n*O+o)*M+:M] : '0;
                assign raw_output_ready[n*O+o] = transport && i_tile_rx_ready[J] === 1'b1;
                assign ejection_stall[J] = o_tile_rx_valid[J] && i_tile_rx_ready[J] !== 1'b1;
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
            assign link_destination[l*RW+:RW] = RW'(DST);
            assign link_source[l*(NI+OS)+:(NI+OS)] = (NI+OS)'(
                ((SRC / O) << OS) | (SRC % O));

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
                    .o_bad(link_bad[l])
                );

                assign raw_input_data[DST*D+:D] = packet[0+:D];
                assign raw_input_metadata[DST*M+:M] = packet[D+:M];
            end else if (l < IL || l >= L ||!LINK_PRESENT_MASK[l]) begin : g_absent
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
                    i_boundary_rx_metadata[b*M+:M]);
                wire input_parity_bad = ENABLE_LINK_PARITY && i_boundary_rx_valid[b] === 1'b1 &&
                    (^{i_boundary_rx_parity[b], i_boundary_rx_data[b*D+:D],
                        i_boundary_rx_metadata[b*M+:M]} !== 1'b0);
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
                        i_boundary_rx_valid[b] === 1'b1),
                    .o_ready(ready),
                    .i_data({ENABLE_LINK_PARITY ? i_boundary_rx_parity[b] : 1'b0,
                        i_boundary_rx_metadata[b*M+:M], i_boundary_rx_data[b*D+:D]}),
                    .o_valid(valid),
                    .i_ready(available &&!held_parity_bad && input_ready[DST]),
                    .o_data(packet),
                    .o_count(count),
                    .o_bad(qin_bad)
                );

                assign o_boundary_rx_ready[b] = ingress && available && valid_meta &&
                    !input_parity_bad && ready;
                assign raw_input_valid[DST] = available && valid &&!held_parity_bad;
                assign raw_input_data[DST*D+:D] = input_valid[DST] ? packet[0+:D] : '0;
                assign raw_input_metadata[DST*M+:M] = input_valid[DST] ? packet[D+:M] : '0;
                assign boundary_idle[b] = count == 0;
                assign link_transfer[IN] = i_boundary_rx_valid[b] === 1'b1 &&
                    o_boundary_rx_ready[b];
                assign parity_bad[IN] = run &&!flush_all &&
                    ((ingress && input_parity_bad) || held_parity_bad);
                assign metadata_bad[N*TX+b] = ingress && i_boundary_rx_valid[b] === 1'b1 &&
                    !valid_meta;
                assign metadata_epoch_bad[N*TX+b] = metadata_bad[N*TX+b] && CHECK_CONTEXT &&
                    i_boundary_rx_metadata[b*M+CI+V+K+:EP] !== o_active_epoch;
            end else begin : g_no_input
                assign o_boundary_rx_ready[b] = 1'b0;
                assign boundary_idle[b] = 1'b1;
                assign qin_bad = 1'b0;
                assign metadata_bad[N*TX+b] = 1'b0;
                assign metadata_epoch_bad[N*TX+b] = 1'b0;
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
                        i_boundary_tx_ready[b] === 1'b1),
                    .o_data(packet),
                    .o_count(count),
                    .o_bad(qout_bad)
                );

                assign raw_output_ready[SRC] = available && ready;
                assign o_boundary_tx_valid[b] = available && valid &&!held_parity_bad;
                assign o_boundary_tx_data[b*D+:D] = o_boundary_tx_valid[b] ? packet[0+:D] : '0;
                assign o_boundary_tx_metadata[b*M+:M] = o_boundary_tx_valid[b] ? packet[D+:M] : '0;
                assign o_boundary_tx_parity[b] = o_boundary_tx_valid[b] ? packet[D+M] : 1'b0;
                assign boundary_idle[B+b] = count == 0;
                assign link_transfer[OUT] = o_boundary_tx_valid[b] &&
                    i_boundary_tx_ready[b] === 1'b1;
                assign parity_bad[OUT] = run &&!flush_all && held_parity_bad;
            end else begin : g_no_output
                assign o_boundary_tx_valid[b] = 1'b0;
                assign o_boundary_tx_data[b*D+:D] = '0;
                assign o_boundary_tx_metadata[b*M+:M] = '0;
                assign o_boundary_tx_parity[b] = 1'b0;
                assign boundary_idle[B+b] = 1'b1;
                assign qout_bad = 1'b0;
            end

            assign boundary_bad[b] = qin_bad || qout_bad;
            assign boundary_stall[b] = run && in_present &&!flush_all &&
                i_boundary_rx_valid[b] === 1'b1 &&!o_boundary_rx_ready[b];
            assign boundary_stall[B+b] = o_boundary_tx_valid[b] &&
                i_boundary_tx_ready[b] !== 1'b1;
        end

        // Schedule checking diagnoses violations without changing elastic
        // ownership. Off-slot data is never silently discarded or duplicated.
        always @* begin
            int period;
            period = int'(active_image[40+V+K+P+:PW]);
            schedule_violation = '0;

            if (schedule_check) begin
                for (int n = 0; n < N; n++) begin
                    for (int i = 0; i < I; i++) begin
                        logic used;
                        int arrival;
                        used = 1'b0;
                        arrival = int'(active_image[ARRIVAL_BASE+(n*I+i)*AW+:AW]);

                        for (int o = 0; o < O; o++)
                            used |= active_image[HEADER+n*O+o] &&
                                active_image[SELECT_BASE+(n*O+o)*S+:S] == S'(i);

                        if (used) begin
                            if (input_valid[n*I+i] && (!due(arrival, period) ||
                                !input_ready[n*I+i])) schedule_violation[n] = 1'b1;

                            if (i_drain === 1'b0 && due(arrival, period) &&
                                !input_valid[n*I+i]) schedule_violation[n] = 1'b1;
                        end
                    end

                    for (int o = 0; o < O; o++) begin
                        int selected;
                        int arrival;
                        selected = int'(active_image[SELECT_BASE+(n*O+o)*S+:S]);
                        arrival = 0;

                        if (selected < I)
                            arrival = 1 + int'(active_image[ARRIVAL_BASE+(n*I+selected)*AW+:AW]);

                        if (active_image[HEADER+n*O+o] && output_valid[n*O+o] &&
                            (!due(arrival, period) ||!output_ready[n*O+o]))
                            schedule_violation[n] = 1'b1;
                    end
                end
            end
        end

        always @* begin
            runtime_code = MESH_OK;
            runtime_node = '0;
            runtime_link = '0;

            if (|counter_overflow) runtime_code = MESH_ERR_COUNTER;

            if (|node_error) runtime_code = MESH_ERR_UNKNOWN;

            if (run &&!flush_all) begin
                for (int n = 0; n < N; n++) begin
                    if (NODE_PRESENT_MASK[n] &&
                        ((^i_tile_tx_valid[n*TX+:TX] === 1'bx) ||
                        (|(o_tile_rx_valid[n*RX+:RX]) &&
                            (^i_tile_rx_ready[n*RX+:RX] === 1'bx))))
                        runtime_code = MESH_ERR_UNKNOWN;
                end

                if (i_link_fault_valid === 1'b1 && (^i_link_fault_mask === 1'bx))
                    runtime_code = MESH_ERR_UNKNOWN;

                if (EXPOSE_BOUNDARY_PORTS &&
                    ((^i_boundary_rx_valid === 1'bx) ||
                    ((|o_boundary_tx_valid) && (^i_boundary_tx_ready === 1'bx))))
                    runtime_code = MESH_ERR_UNKNOWN;
            end

            for (int n = N - 1; n >= 0; n--) begin
                if (schedule_violation[n]) begin
                    runtime_code = MESH_ERR_SCHEDULE;
                    runtime_node = NI'(n);
                end
            end

            for (int i = N * TX + B - 1; i >= 0; i--) begin
                if (metadata_bad[i]) begin
                    runtime_code = metadata_epoch_bad[i] ? MESH_ERR_EPOCH : MESH_ERR_METADATA;
                    runtime_node = NI'(i < N * TX ? i / TX :
                        destination_resource(IL + 2 * (i - N * TX)) / I);
                end
            end

            for (int l = L - 1; l >= 0; l--) begin
                if (parity_bad[l]) begin
                    runtime_code = MESH_ERR_PARITY;
                    runtime_link = LI'(l);
                    runtime_node = NI'(l >= IL && (l - IL) % 2 == 1 ?
                        source_resource(l) / O : destination_resource(l) / I);
                end
            end

            if (o_active_link_fault) runtime_code = MESH_ERR_FAULTED;
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

        // Events describe the immediately preceding sampling edge.
        dff #(
            .WIDTH(2 * LB + N * (TX + RX + 2) + 2 * B),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_events (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d({link_transfer, parity_pulse, injection_stall, ejection_stall,
                boundary_stall, multicast, schedule_violation}),
            .o_q({o_directed_link_active, o_parity_error_event, o_tile_injection_stall,
                o_tile_ejection_stall, o_boundary_stall, o_multicast_event,
                o_schedule_violation})
        );

        // Counter map: 0..15 global, then offered/accepted TX, offered/delivered
        // RX, transfer/active/error links, four boundary counters, four per node.
        // N node high-water marks and one mesh high-water mark follow the bank.
        localparam int TX_BASE = 16;
        localparam int RX_BASE = TX_BASE + 2 * N * TX;
        localparam int LINK_BASE = RX_BASE + 2 * N * RX;
        localparam int BOUNDARY_BASE = LINK_BASE + 3 * LB;
        localparam int NODE_BASE = BOUNDARY_BASE + 4 * B;
        logic [COUNTERS*16-1:0] increments;

        wire [31:0] counter_values [COUNTERS];
        wire [32:0] counter_read;
        wire [31:0] counter_data;
        wire read_valid;
        logic [N*32+32-1:0] peaks_next;
        wire [N*32+32-1:0] peaks;
        logic [31:0] selected_peak;
        wire peak_read = i_counter_read === 1'b1 && (^i_counter_index !== 1'bx) &&
            int'(i_counter_index) >= COUNTERS &&
            int'(i_counter_index) <= COUNTERS + N;
        wire [32:0] peak_result;

        always @* begin
            int occupancy;
            int total;
            total = 0;
            increments = '0;
            peaks_next = peaks;
            increments[0*16+:16] = 16'(ingress && (|i_tile_tx_valid));
            increments[1*16+:16] = 16'($countones(i_tile_tx_valid & o_tile_tx_ready));
            increments[2*16+:16] = 16'($countones(o_tile_rx_valid & i_tile_rx_ready));
            increments[3*16+:16] = 16'($countones(link_transfer));
            increments[4*16+:16] = 16'(activation);
            increments[5*16+:16] = 16'(run && i_drain === 1'b1);
            increments[6*16+:16] = 16'(run && i_flush === 1'b1);
            increments[7*16+:16] = 16'(o_active_link_fault);
            increments[8*16+:16] = 16'($countones(schedule_violation));
            increments[9*16+:16] = 16'($countones(parity_pulse));
            increments[10*16+:16] = 16'($countones(multicast));
            increments[11*16+:16] = 16'($countones(metadata_bad));
            increments[12*16+:16] = 16'(all_idle);
            increments[13*16+:16] = 16'($countones(injection_stall));
            increments[14*16+:16] = 16'($countones(ejection_stall));
            increments[15*16+:16] = 16'(configuration_busy);

            for (int j = 0; j < N * TX; j++) begin
                increments[(TX_BASE+2*j)*16+:16] = 16'(i_tile_tx_valid[j] === 1'b1);
                increments[(TX_BASE+2*j+1)*16+:16] =
                    16'(i_tile_tx_valid[j] === 1'b1 && o_tile_tx_ready[j]);
            end

            for (int j = 0; j < N * RX; j++) begin
                increments[(RX_BASE+2*j)*16+:16] = 16'(o_tile_rx_valid[j]);
                increments[(RX_BASE+2*j+1)*16+:16] =
                    16'(o_tile_rx_valid[j] && i_tile_rx_ready[j] === 1'b1);
            end

            for (int l = 0; l < LB; l++) begin
                increments[(LINK_BASE+3*l)*16+:16] = 16'(link_transfer[l]);
                increments[(LINK_BASE+3*l+1)*16+:16] =
                    16'(l < L && LINK_PRESENT_MASK[l] &&!link_idle[l]);
                increments[(LINK_BASE+3*l+2)*16+:16] = 16'(parity_pulse[l]);
            end

            for (int b = 0; b < B; b++) begin
                increments[(BOUNDARY_BASE+4*b)*16+:16] =
                    16'(i_boundary_rx_valid[b] === 1'b1 && o_boundary_rx_ready[b]);
                increments[(BOUNDARY_BASE+4*b+1)*16+:16] =
                    16'(o_boundary_tx_valid[b] && i_boundary_tx_ready[b] === 1'b1);
                increments[(BOUNDARY_BASE+4*b+2)*16+:16] = 16'(boundary_stall[b]);
                increments[(BOUNDARY_BASE+4*b+3)*16+:16] = 16'(boundary_stall[B+b]);
            end

            for (int n = 0; n < N; n++) begin
                occupancy = $countones(o_node_buffered[n*I+:I]);
                total += occupancy;
                increments[(NODE_BASE+4*n)*16+:16] = 16'(occupancy);
                increments[(NODE_BASE+4*n+1)*16+:16] = 16'(node_idle[n]);
                increments[(NODE_BASE+4*n+2)*16+:16] = 16'(!o_node_clock_enable[n]);
                increments[(NODE_BASE+4*n+3)*16+:16] = 16'(schedule_violation[n]);
                if (32'(occupancy) > peaks[n*32+:32]) peaks_next[n*32+:32] = 32'(occupancy);
            end

            if (32'(total) > peaks[N*32+:32]) peaks_next[N*32+:32] = 32'(total);

            selected_peak = '0;

            if (peak_read) selected_peak = peaks[(int'(i_counter_index)-COUNTERS)*32+:32];
        end

        dff #(.WIDTH((N + 1) * 32), .ASYNC_RESET(ASYNC_RESET)) u_peaks (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d(peaks_next),
            .o_q(peaks)
        );

        dff #(.WIDTH(33), .ASYNC_RESET(ASYNC_RESET)) u_peak_read (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d({peak_read, selected_peak}),
            .o_q(peak_result)
        );

        for (genvar c = 0; c < COUNTERS; c++) begin : g_counter_binding
            wire [32:0] sum = {1'b0, counter_values[c]} +
                33'(increments[c*16+:16]);

            // Keep each readback word on its own net. A single concatenated
            // bank bus creates unnecessary fanout through every observation mux.
            banked_scratchpad_counters #(
                .COUNT(1),
                .PEAKS(1),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_counter (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_increments(32'(increments[c*16+:16])),
                .i_occupancy(32'b0),
                .o_counts(counter_values[c]),
                .o_peaks()
            );

            assign counter_overflow[c] = run && sum[32];
        end

        dff #(.WIDTH(33), .ASYNC_RESET(ASYNC_RESET)) u_counter_read (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d({i_counter_read === 1'b1 && (^i_counter_index !== 1'bx) &&
                int'(i_counter_index) < COUNTERS,
                int'(i_counter_index) < COUNTERS ?
                    counter_values[i_counter_index] : 32'b0}),
            .o_q(counter_read)
        );

        assign read_valid = counter_read[32];
        assign counter_data = counter_read[0+:32];
        assign o_counter_valid = run && (read_valid || peak_result[32]);
        assign o_counter_value = !o_counter_valid ? '0 : peak_result[32] ?
            peak_result[0+:32] : counter_data;
    end
endmodule
`default_nettype wire
