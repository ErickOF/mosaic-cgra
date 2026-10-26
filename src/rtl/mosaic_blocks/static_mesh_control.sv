`timescale 1ns / 1ps
`default_nettype none

module static_mesh_control #(
    parameter int N = 16,
    parameter int I = 6,
    parameter int O = 6,
    parameter int TX = 2,
    parameter int RX = 2,
    parameter int H = 1,
    parameter int D = 32,
    parameter int M = 64,
    parameter int CD = 4,
    parameter int W = 64,
    parameter int CI = 8,
    parameter int V = 16,
    parameter int K = 16,
    parameter int EP = 2,
    parameter int P = 32,
    parameter int PM = 256,
    parameter int B = 16,
    parameter int IL = 48,
    parameter int L = 80,
    parameter int LB = 80,
    parameter int LI = 7,
    parameter int LX = 7,
    parameter int NI = 4,
    parameter int S = 3,
    parameter int OS = 3,
    parameter int RW = 7,
    parameter int AW = 15,
    parameter int PW = 9,
    parameter int HEADER = 114,
    parameter int IMAGE = 2610,
    parameter int WORDS = 41,
    parameter int IM = 2624,
    parameter int WI = 6,
    parameter int COUNTERS = 544,
    parameter int CW = 10,
    parameter int FLOW_PROFILE = 0,
    parameter int BOUNDARY_BUFFER_DEPTH = 1,
    parameter int CHECK_CONTEXT = 1,
    parameter int ENABLE_LINK_PARITY = 0,
    parameter int CONTROL_PROTECTION = 0,
    parameter int SUPPORT_LINK_EXCLUSION = 1,
    parameter int SUPPORT_MULTICAST = 1,
    parameter int MAX_MULTICAST_FANOUT = 4,
    parameter int ASYNC_RESET = 0,
    parameter int TOPOLOGY_ID = 32'b0
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_enable,
    input wire i_drain,
    input wire i_flush,
    input wire i_error_clear,
    input wire i_boundary_isolate,
    input wire i_test_enable,
    input wire i_scan_enable,
    input wire i_cfg_valid,
    output wire o_cfg_ready,
    input wire [2:0] i_cfg_opcode,
    input wire [CI-1:0] i_cfg_context_id,
    input wire [V-1:0] i_cfg_context_version,
    input wire [WI-1:0] i_cfg_word_index,
    input wire [W-1:0] i_cfg_write_data,
    input wire [W/8-1:0] i_cfg_write_strobe,
    input wire [K-1:0] i_cfg_kernel_id,
    input wire [P-1:0] i_cfg_proof_id,
    input wire [31:0] i_cfg_checksum,
    output wire o_cfg_rsp_valid,
    input wire i_cfg_rsp_ready,
    output wire [CI-1:0] o_cfg_rsp_context_id,
    output wire [V-1:0] o_cfg_rsp_context_version,
    output wire [W-1:0] o_cfg_rsp_read_data,
    output wire [31:0] o_cfg_rsp_checksum,
    output wire o_cfg_rsp_error,
    output wire [7:0] o_cfg_rsp_error_code,
    output wire o_active_context_valid,
    output wire [CI-1:0] o_active_context_id,
    output wire [V-1:0] o_active_context_version,
    output wire [K-1:0] o_active_kernel_id,
    output wire [EP-1:0] o_active_epoch,
    output wire [CD-1:0] o_context_valid,
    input wire i_link_fault_valid,
    output wire o_link_fault_ready,
    input wire [LB-1:0] i_link_fault_mask,
    output wire [LB-1:0] o_faulted_link_mask,
    output wire o_active_link_fault,
    output wire o_error,
    output wire [7:0] o_error_code,
    output wire [NI-1:0] o_error_node,
    output wire [LI-1:0] o_error_link,
    output wire o_quiescent,
    output wire o_drained,
    output wire o_flush_completed,
    output wire o_boundary_isolated,
    input wire i_all_idle,
    input wire i_nodes_ready,
    input wire i_nodes_match,
    input wire i_integrity_bad,
    input wire [7:0] i_runtime_code,
    input wire [NI-1:0] i_runtime_node,
    input wire [LI-1:0] i_runtime_link,
    input wire [N*O*I-1:0] i_connectivity,
    input wire [N-1:0] i_node_present,
    input wire [LB-1:0] i_link_present,
    input wire [N*I*LX-1:0] i_input_links,
    input wire [N*O*LX-1:0] i_output_links,
    input wire [LB*RW-1:0] i_link_destination,
    input wire [LB*(NI+OS)-1:0] i_link_source,
    output wire [IM-1:0] o_active_image,
    output wire o_ingress_permitted,
    output wire o_transport_permitted,
    output wire o_install_valid,
    output wire o_flush_all,
    output wire [31:0] o_schedule_tick,
    output wire o_schedule_check,
    output wire o_activation_event,
    output wire o_configuration_busy,
    output wire [CI-1:0] o_install_context,
    output wire o_route_check
);
    import static_mesh_pkg::*;

    localparam int Y = IM / 8;
    localparam int A = CD > 1 ? $clog2(CD) : 1;
    localparam int CODE = code_width(IM);
    localparam int STORED = (CODE + 7) / 8 * 8;
    localparam int ENABLE_BASE = HEADER;
    localparam int SELECT_BASE = ENABLE_BASE + N * O;
    localparam int RANK_BASE = SELECT_BASE + N * O * S;
    localparam int ARRIVAL_BASE = RANK_BASE + N * I * RW;

    typedef struct packed {
        logic loading;
        logic valid;
        logic [Y-1:0] written;
        logic [V-1:0] version;
        logic [K-1:0] kernel;
        logic [P-1:0] proof;
        logic [31:0] checksum;
    } context_t;

    typedef struct packed {
        control_phase_t phase;
        logic active;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [K-1:0] kernel;
        logic [EP-1:0] epoch;
        logic [LB-1:0] fault_mask;
        logic flush_seen;
        logic flush_pending;
        logic flush_pulse;
        logic isolated;
        logic schedule_started;
        logic [31:0] tick;
        logic fatal;
        logic [7:0] code;
        logic [NI-1:0] error_node;
        logic [LI-1:0] error_link;
        logic activation;
    } control_t;

    typedef struct packed {
        logic valid;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [W-1:0] data;
        logic [31:0] checksum;
        logic [7:0] code;
    } response_t;

    localparam int CTX = $bits(context_t);
    wire run = i_reset_n === 1'b1;
    wire global_known = (^{i_enable, i_drain, i_flush, i_error_clear,
        i_boundary_isolate, i_test_enable, i_scan_enable, i_cfg_valid,
        i_cfg_rsp_ready, i_link_fault_valid} !== 1'bx);
    wire [CTX-1:0] contexts [CD];
    logic [CTX-1:0] context_next [CD];
    wire [CD-1:0] context_bad;
    control_t q;
    control_t n;
    response_t response;
    response_t response_next;
    wire control_bad;
    wire response_bad;
    wire active_bad;
    wire integrity_bad = control_bad || response_bad || active_bad || (|context_bad) ||
        i_integrity_bad;
    wire [IM-1:0] active_image;
    logic [IM-1:0] active_next;
    wire [STORED-1:0] raw_context;
    wire raw_context_valid;
    wire [IM-1:0] decoded_image;
    wire image_bad;
    wire [CODE-1:0] encoded_image;
    logic [IM-1:0] write_image;
    logic [Y-1:0] write_bytes;
    logic write_memory;
    logic commit_memory;
    logic invalidate_memory;
    context_t selected;
    assign selected = int'(i_cfg_context_id) < CD ? contexts[i_cfg_context_id] : {CTX{1'b0}};
    logic [IM-1:0] sanitized_image;
    logic [LB-1:0] active_links;
    logic [LB-1:0] candidate_links;
    logic [N*I-1:0] candidate_used;
    logic [7:0] validation_code;
    logic [7:0] command_code;
    wire cfg_fire = i_cfg_valid === 1'b1 && o_cfg_ready;
    wire fault_fire = i_link_fault_valid === 1'b1 && o_link_fault_ready;
    wire empty_boundary = i_all_idle && q.phase == MESH_CONTROL_READY &&!response.valid;
    wire valid_context_index = (^i_cfg_context_id !== 1'bx) && int'(i_cfg_context_id) < CD;
    wire [PW-1:0] active_period = active_image[40+V+K+P+:PW];
    wire pause_allowed = active_image[HEADER-1];
    wire paused = pause_allowed && i_enable === 1'b0 && i_all_idle;
    wire [31:0] tick_modulus = 32'((N * I + 1) * (PM + 1) + 4) +
        (active_period == 0 ? 32'd1 : 32'(active_period));

    function automatic int code_width(input int width);
        int stripes;
        int last;
        int parity_bits;
        stripes = (width + 255) / 256;
        last = width - (stripes - 1) * 256;
        parity_bits = 1;

        while ((64'd1 << parity_bits) < 64'(last) + 64'(parity_bits) + 1) parity_bits++;

        return CONTROL_PROTECTION == 2 ?
            (stripes - 1) * 266 + last + parity_bits + 1 : width + CONTROL_PROTECTION;
    endfunction

    function automatic logic [31:0] checksum(input logic [IM-1:0] value);
        logic [31:0] crc;
        crc = 32'hffffffff;

        for (int b = 0; b < IM / 8; b++) begin
            crc = crc ^ {24'b0, value[b*8+:8]};

            for (int k = 0; k < 8; k++) crc = crc[0] ?
                (crc >> 1) ^ 32'h82f63b78 : crc >> 1;
        end

        return ~crc;
    endfunction

    function automatic logic [LB-1:0] required_links(input logic [IM-1:0] image);
        logic [LB-1:0] required;
        int input_index;
        int link_index;
        required = '0;

        for (int node = 0; node < N; node++) begin
            for (int o = 0; o < O; o++) begin
                if (image[ENABLE_BASE+node*O+o]) begin
                    input_index = int'(image[SELECT_BASE+(node*O+o)*S+:S]);
                    link_index = int'(i_output_links[(node*O+o)*LX+:LX]);

                    if (link_index < L) required[link_index] = 1'b1;

                    if (input_index < I) begin
                        link_index = int'(i_input_links[(node*I+input_index)*LX+:LX]);

                        if (link_index < L) required[link_index] = 1'b1;
                    end
                end
            end
        end

        return required;
    endfunction

    always @* begin
        sanitized_image = '0;

        for (int b = 0; b < Y; b++)
            if ((selected.written >> b) & 1'b1)
                sanitized_image[b*8+:8] = decoded_image[b*8+:8];
    end

    always @* begin
        active_links = required_links(active_image);
        candidate_links = required_links(sanitized_image);
        candidate_used = '0;

        for (int node = 0; node < N; node++) begin
            for (int o = 0; o < O; o++) begin
                int source;
                source = int'(sanitized_image[SELECT_BASE+(node*O+o)*S+:S]);

                if (sanitized_image[ENABLE_BASE+node*O+o] && source < I)
                    candidate_used[node*I+source] = 1'b1;
            end
        end
    end

    // A rank certificate proves acyclic input-resource dependencies locally.
    // Schedule offsets prove registered-hop timing without computing routes.
    always @* begin
        logic [IM-1:0] proof_image;
        logic [PW-1:0] period;
        logic [P-1:0] proof;
        period = sanitized_image[40+V+K+P+:PW];
        proof = sanitized_image[40+V+K+:P];
        proof_image = sanitized_image;
        proof_image[40+V+K+:P] = '0;
        validation_code = MESH_OK;

        if (selected.written != {Y{1'b1}}) validation_code = MESH_ERR_INCOMPLETE;
        else if (image_bad) validation_code = MESH_ERR_INTEGRITY;
        else if (sanitized_image[0+:8] != 1 || sanitized_image[8+:32] != 32'(TOPOLOGY_ID) ||
            (sanitized_image >> IMAGE) != 0) validation_code = MESH_ERR_PROOF;
        else if (sanitized_image[40+:V] != selected.version ||
            i_cfg_context_version != selected.version) validation_code = MESH_ERR_VERSION;
        else if (sanitized_image[40+V+:K] != selected.kernel ||
            i_cfg_kernel_id != selected.kernel) validation_code = MESH_ERR_KERNEL;
        else if (proof == 0 || proof != i_cfg_proof_id ||
            proof != P'(checksum(proof_image) ^ 32'(TOPOLOGY_ID))) validation_code = MESH_ERR_PROOF;
        else if (checksum(sanitized_image) != i_cfg_checksum) validation_code = MESH_ERR_CHECKSUM;
        else if ((candidate_links & ~i_link_present) != 0) validation_code = MESH_ERR_PHYSICAL;
        else if (SUPPORT_LINK_EXCLUSION && (candidate_links & q.fault_mask) != 0)
            validation_code = MESH_ERR_FAULTED;
        else if (period == 0 || int'(period) > PM) validation_code = MESH_ERR_SCHEDULE;

        for (int node = 0; node < N; node++) begin
            for (int o = 0; o < O; o++) begin
                int source;
                int link_index;
                int destination;
                int source_rank;
                int destination_rank;
                int offset;
                int destination_offset;
                int fanout;
                source = int'(sanitized_image[SELECT_BASE+(node*O+o)*S+:S]);
                link_index = int'(i_output_links[(node*O+o)*LX+:LX]);
                source_rank = 0;
                offset = 0;

                if (source < I) begin
                    source_rank = int'(sanitized_image[RANK_BASE+(node*I+source)*RW+:RW]);
                    offset = int'(sanitized_image[ARRIVAL_BASE+(node*I+source)*AW+:AW]);
                end

                fanout = 0;

                for (int other = 0; other < O; other++)
                    if (sanitized_image[ENABLE_BASE+node*O+other] &&
                        sanitized_image[SELECT_BASE+(node*O+other)*S+:S] == S'(source)) fanout++;

                if (validation_code == MESH_OK && sanitized_image[ENABLE_BASE+node*O+o]) begin
                    if (!i_node_present[node] || source >= I ||
                        !i_connectivity[node*O*I+o*I+source]) validation_code = MESH_ERR_ROUTE;
                    else if (fanout > MAX_MULTICAST_FANOUT ||
                        (SUPPORT_MULTICAST == 0 && fanout > 1)) validation_code = MESH_ERR_FANOUT;
                    else if (offset > (N * I + 1) * (PM + 1))
                        validation_code = MESH_ERR_SCHEDULE;
                    else if (source_rank >= N * I) validation_code = MESH_ERR_PROOF;
                    else if (o >= RX && link_index < IL) begin
                        destination = int'(i_link_destination[link_index*RW+:RW]);
                        destination_rank = int'(sanitized_image[RANK_BASE+destination*RW+:RW]);
                        destination_offset = int'(sanitized_image[ARRIVAL_BASE+destination*AW+:AW]);
                        if (destination >= N * I ||!candidate_used[destination] ||
                            destination_rank <= source_rank) validation_code = MESH_ERR_PROOF;
                        else if (FLOW_PROFILE == 1 && destination_offset != offset + 1)
                            validation_code = MESH_ERR_SCHEDULE;
                    end

                    if (validation_code == MESH_OK && source >= TX) begin
                        int provider;
                        int provider_node;
                        int provider_direction;
                        int input_link_index;
                        input_link_index = int'(i_input_links[(node*I+source)*LX+:LX]);

                        if (input_link_index < IL) begin
                            provider = int'(i_link_source[input_link_index*(NI+OS)+:(NI+OS)]);
                            provider_node = provider >> OS;
                            provider_direction = provider & ((1 << OS) - 1);

                            if (!sanitized_image[ENABLE_BASE+provider_node*O+provider_direction])
                                validation_code = MESH_ERR_PROOF;
                        end else if (FLOW_PROFILE == 1 && BOUNDARY_BUFFER_DEPTH > 0 && offset == 0)
                            validation_code = MESH_ERR_SCHEDULE;
                    end
                end
            end
        end
    end

    assign o_active_image = active_image;
    assign o_install_context = q.context_id;
    assign o_active_context_valid = run && q.active && q.phase == MESH_CONTROL_READY &&
        !integrity_bad &&!q.fatal;
    assign o_route_check = run && q.active && q.phase == MESH_CONTROL_READY &&
        !control_bad &&!active_bad;
    assign o_active_context_id = o_active_context_valid ? q.context_id : '0;
    assign o_active_context_version = o_active_context_valid ? q.version : '0;
    assign o_active_kernel_id = o_active_context_valid ? q.kernel : '0;
    assign o_active_epoch = run &&!control_bad ? q.epoch : {EP{1'b0}};
    assign o_faulted_link_mask = run &&!control_bad ? q.fault_mask : {LB{1'b0}};
    assign o_active_link_fault = run &&!control_bad &&!active_bad && q.active &&
        (|(active_links & q.fault_mask));
    assign o_error = run && (q.code != MESH_OK || integrity_bad);
    assign o_error_code = !run ? MESH_OK : integrity_bad ? MESH_ERR_INTEGRITY : q.code;
    assign o_error_node = run &&!control_bad ? q.error_node : '0;
    assign o_error_link = run &&!control_bad ? q.error_link : '0;
    assign o_transport_permitted = run && global_known && i_flush === 1'b0 &&
        !q.flush_pending && q.phase == MESH_CONTROL_READY &&!integrity_bad &&!q.fatal;
    assign o_ingress_permitted = o_transport_permitted && q.active && q.code == MESH_OK &&
        !o_active_link_fault && i_enable === 1'b1 && i_drain === 1'b0 &&
        i_boundary_isolate === 1'b0 &&!q.isolated && i_cfg_valid === 1'b0 &&
        i_link_fault_valid === 1'b0;
    assign o_install_valid = run && global_known && i_flush === 1'b0 &&
        !q.flush_pending && q.phase == MESH_CONTROL_INSTALL &&!integrity_bad;
    assign o_flush_all = run && i_flush === 1'b1;
    assign o_quiescent = run && global_known && empty_boundary &&!integrity_bad &&
        !q.flush_pending &&
        i_flush === 1'b0;
    assign o_drained = o_quiescent && i_drain === 1'b1;
    assign o_flush_completed = run && q.flush_pulse;
    assign o_boundary_isolated = run && q.isolated;
    assign o_schedule_tick = q.tick;
    assign o_schedule_check = FLOW_PROFILE == 1 && o_transport_permitted && q.active &&
        (q.schedule_started || i_enable === 1'b1) &&!paused && i_error_clear === 1'b0;
    assign o_configuration_busy = run && (q.phase != MESH_CONTROL_READY || response.valid);
    assign o_activation_event = run && q.activation;
    assign o_cfg_ready = run && global_known && i_flush === 1'b0 &&!q.flush_pending &&
        q.phase == MESH_CONTROL_READY && (!response.valid || i_cfg_rsp_ready === 1'b1) &&
        i_link_fault_valid === 1'b0 &&!integrity_bad;
    assign o_link_fault_ready = run && global_known && SUPPORT_LINK_EXCLUSION == 1 &&
        (^i_link_fault_mask !== 1'bx) && i_flush === 1'b0 &&!q.flush_pending &&
        q.phase == MESH_CONTROL_READY &&!response.valid && i_cfg_valid === 1'b0 &&
        (i_all_idle || (q.fault_mask & ~i_link_fault_mask) == 0) &&
        (i_link_fault_mask & ~i_link_present) == 0;
    assign o_cfg_rsp_valid = run && i_flush === 1'b0 &&!response_bad && response.valid;
    assign o_cfg_rsp_context_id = !response_bad ? response.context_id : '0;
    assign o_cfg_rsp_context_version = !response_bad ? response.version : '0;
    assign o_cfg_rsp_read_data = !response_bad ? response.data : '0;
    assign o_cfg_rsp_checksum = !response_bad ? response.checksum : '0;
    assign o_cfg_rsp_error = !response_bad && response.code != MESH_OK;
    assign o_cfg_rsp_error_code = !response_bad ? response.code : MESH_ERR_INTEGRITY;

    // Configuration is serialized. Payload storage remains unreset; the protected
    // byte-written directory decides which raw bytes are meaningful.
    always @* begin
        command_code = MESH_OK;

        if ((^{i_cfg_opcode, i_cfg_context_id, i_cfg_context_version,
            i_cfg_kernel_id} === 1'bx)) command_code = MESH_ERR_UNKNOWN;
        else if (!valid_context_index) command_code = MESH_ERR_CONTEXT;
        else if (i_cfg_opcode > MESH_CFG_QUERY) command_code = MESH_ERR_COMMAND;
        else if ((i_cfg_opcode == MESH_CFG_WRITE || i_cfg_opcode == MESH_CFG_INVALIDATE) &&
            q.active && i_cfg_context_id == q.context_id) command_code = MESH_ERR_ACTIVE;
        else if (i_cfg_opcode == MESH_CFG_WRITE) begin
            if (^{i_cfg_word_index, i_cfg_write_data, i_cfg_write_strobe} === 1'bx)
                command_code = MESH_ERR_UNKNOWN;
            else if (int'(i_cfg_word_index) >= WORDS) command_code = MESH_ERR_WORD;
            else if ((selected.loading && i_cfg_context_version != selected.version) ||
                (!selected.loading && i_cfg_context_version <= selected.version))
                command_code = MESH_ERR_VERSION;
            else if (selected.loading && i_cfg_kernel_id != selected.kernel)
                command_code = MESH_ERR_KERNEL;
            else if (selected.written != 0 && image_bad) command_code = MESH_ERR_INTEGRITY;
        end else if (i_cfg_context_version != selected.version)
            command_code = MESH_ERR_VERSION;
        else if (i_cfg_opcode == MESH_CFG_READ) begin
            if (^i_cfg_word_index === 1'bx) command_code = MESH_ERR_UNKNOWN;
            else if (int'(i_cfg_word_index) >= WORDS) command_code = MESH_ERR_WORD;
            else if (selected.written != 0 && image_bad) command_code = MESH_ERR_INTEGRITY;
        end else if (i_cfg_opcode == MESH_CFG_VALIDATE) begin
            if (^{i_cfg_checksum, i_cfg_proof_id} === 1'bx) command_code = MESH_ERR_UNKNOWN;
            else command_code = validation_code;
        end else if (i_cfg_opcode == MESH_CFG_ACTIVATE) begin
            if (!selected.valid ||!raw_context_valid) command_code = MESH_ERR_INCOMPLETE;
            else if (!i_all_idle || q.flush_pending || q.fatal ||
                i_boundary_isolate !== 1'b0) command_code = MESH_ERR_BUSY;
            else if (image_bad) command_code = MESH_ERR_INTEGRITY;
            else if (i_cfg_kernel_id != selected.kernel) command_code = MESH_ERR_KERNEL;
            else if (i_cfg_proof_id !== selected.proof) command_code = MESH_ERR_PROOF;
            else if (SUPPORT_LINK_EXCLUSION && (candidate_links & q.fault_mask) != 0)
                command_code = MESH_ERR_FAULTED;
        end
    end

    always @* begin
        context_t updated;
        n = q;
        response_next = response;
        active_next = active_image;
        write_image = sanitized_image;
        write_bytes = selected.written;
        write_memory = 1'b0;
        commit_memory = 1'b0;
        invalidate_memory = 1'b0;
        n.flush_pulse = 1'b0;
        n.activation = 1'b0;
        updated = selected;

        for (int c = 0; c < CD; c++) context_next[c] = contexts[c];

        if (run && i_flush === 1'b0 && response.valid && i_cfg_rsp_ready === 1'b1)
            response_next.valid = 1'b0;

        if (run && global_known &&!q.flush_pending && i_flush === 1'b0) begin
            if (q.phase == MESH_CONTROL_INSTALL && i_nodes_ready)
                n.phase = MESH_CONTROL_ACK;

            if (q.phase == MESH_CONTROL_ACK) begin
                n.phase = MESH_CONTROL_READY;
                response_next.valid = 1'b1;
                response_next.code = i_nodes_match ? MESH_OK : MESH_ERR_INTEGRITY;

                if (i_nodes_match) n.activation = 1'b1;
                else begin
                    n.code = MESH_ERR_INTEGRITY;
                    n.fatal = 1'b1;
                end
            end

            if (fault_fire) n.fault_mask = i_link_fault_mask;

            if (cfg_fire) begin
                response_next = '0;
                response_next.valid = 1'b1;
                response_next.context_id = (^i_cfg_context_id !== 1'bx) ?
                    i_cfg_context_id : '0;
                response_next.version = valid_context_index ? selected.version : '0;
                response_next.code = command_code;
                response_next.checksum = valid_context_index ? selected.checksum : '0;

                if (command_code == MESH_OK) begin
                    case (i_cfg_opcode)
                        MESH_CFG_WRITE: begin
                            if (|i_cfg_write_strobe) begin
                                if (!selected.loading) begin
                                    write_image = '0;
                                    write_bytes = '0;
                                end

                                for (int b = 0; b < W / 8; b++) begin
                                    if (i_cfg_write_strobe[b]) begin
                                        write_image[(int'(i_cfg_word_index)*W)+b*8+:8] =
                                            i_cfg_write_data[b*8+:8];
                                        write_bytes[int'(i_cfg_word_index)*(W/8)+b] = 1'b1;
                                    end
                                end

                                updated.loading = 1'b1;
                                updated.valid = 1'b0;
                                updated.written = write_bytes;
                                updated.version = i_cfg_context_version;
                                updated.kernel = i_cfg_kernel_id;
                                updated.proof = '0;
                                updated.checksum = '0;
                                write_memory = 1'b1;
                                response_next.version = i_cfg_context_version;
                            end
                        end
                        MESH_CFG_READ: response_next.data =
                            sanitized_image[int'(i_cfg_word_index)*W+:W];
                        MESH_CFG_VALIDATE: begin
                            updated.valid = 1'b1;
                            updated.loading = 1'b0;
                            updated.proof = i_cfg_proof_id;
                            updated.checksum = checksum(sanitized_image);
                            response_next.checksum = updated.checksum;
                            commit_memory = 1'b1;
                        end
                        MESH_CFG_ACTIVATE: begin
                            n.phase = MESH_CONTROL_INSTALL;
                            n.active = 1'b1;
                            n.context_id = i_cfg_context_id;
                            n.version = selected.version;
                            n.kernel = selected.kernel;
                            n.epoch = q.epoch + 1'b1;
                            n.schedule_started = 1'b0;
                            n.tick = '0;
                            active_next = sanitized_image;
                            response_next.valid = 1'b0;
                        end
                        MESH_CFG_INVALIDATE: begin
                            updated.valid = 1'b0;
                            updated.loading = 1'b0;
                            updated.written = '0;
                            invalidate_memory = 1'b1;
                        end
                        MESH_CFG_QUERY: response_next.data = W'({selected.proof,
                            selected.kernel, selected.version, selected.loading, selected.valid});
                        default: begin end
                    endcase
                end else if (valid_context_index && i_cfg_opcode == MESH_CFG_VALIDATE) begin
                    updated.valid = 1'b0;
                    invalidate_memory = 1'b1;
                end

                if (valid_context_index) context_next[i_cfg_context_id] = updated;
            end

            if (i_boundary_isolate === 1'b0) n.isolated = 1'b0;
            else if (empty_boundary) n.isolated = 1'b1;

            if (FLOW_PROFILE == 1 && q.active && q.phase == MESH_CONTROL_READY &&
                !paused && (q.schedule_started || i_enable === 1'b1)) begin
                n.schedule_started = 1'b1;

                // Rebase after every startup offset has passed. Subtracting a
                // whole period preserves every future slot without time wrap.
                n.tick = q.tick + 1'b1;

                if (q.tick >= tick_modulus) n.tick = q.tick + 1'b1 - 32'(active_period);
            end
        end

        if (run && i_flush === 1'b0) n.flush_seen = 1'b0;

        if (run && i_flush === 1'b1 &&!q.flush_seen) begin
            n.flush_seen = 1'b1;
            n.flush_pending = 1'b1;
            n.epoch = q.epoch + 1'b1;
            n.schedule_started = 1'b0;
            n.tick = '0;
        end

        if (run && q.flush_pending && i_all_idle) begin
            n.flush_pending = 1'b0;
            n.flush_pulse = 1'b1;
        end

        if (run && o_quiescent && i_error_clear === 1'b1 &&!integrity_bad &&
            !o_active_link_fault && i_runtime_code == MESH_OK && global_known &&!q.fatal) begin
            n.code = MESH_OK;
            n.error_node = '0;
            n.error_link = '0;
            n.schedule_started = 1'b0;
            n.tick = '0;
        end

        if (run && (integrity_bad ||!global_known || i_runtime_code != MESH_OK)) begin
            if (q.code == MESH_OK) begin
                n.code = integrity_bad ? MESH_ERR_INTEGRITY :
                    !global_known ? MESH_ERR_UNKNOWN : i_runtime_code;
                n.error_node = i_runtime_node;
                n.error_link = i_runtime_link;

                // A bitmap update can fault several routes at once. Retain
                // the lowest affected directed link, not an unrelated input.
                if (o_active_link_fault) begin
                    for (int l = L - 1; l >= 0; l--) begin
                        if (active_links[l] && ((q.fault_mask >> l) & 1'b1)) begin
                            n.error_link = LI'(l);

                            if (l < IL || (l - IL) % 2 == 0)
                                n.error_node = NI'(i_link_destination[l*RW+:RW] / I);
                            else n.error_node = NI'(
                                i_link_source[l*(NI+OS)+:(NI+OS)] >> OS);
                        end
                    end
                end
            end

            if (integrity_bad) n.fatal = 1'b1;
        end
    end

    context_memory #(
        .CONTEXT_WIDTH(STORED),
        .CONTEXT_DEPTH(CD),
        .WRITE_SLICE_WIDTH(8),
        .NUM_READ_PORTS(1),
        .HAS_RAW_READBACK(1),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_context_memory (
        .i_clk(i_clk),
        .i_rstb(i_reset_n),
        .i_read_enable(run),
        .i_read_raw(1'b1),
        .i_read_address(A'(i_cfg_context_id)),
        .o_read_data(raw_context),
        .o_read_valid(raw_context_valid),
        .i_write_enable(write_memory),
        .i_write_mask({(STORED/8){1'b1}}),
        .i_write_address(A'(i_cfg_context_id)),
        .i_write_data(STORED'(encoded_image)),
        .i_commit_enable(commit_memory),
        .i_commit_address(A'(i_cfg_context_id)),
        .i_invalidate_enable(invalidate_memory),
        .i_invalidate_address(A'(i_cfg_context_id))
    );

    tile_shell_codec #(.WIDTH(IM), .PROTECTION(CONTROL_PROTECTION)) u_image_codec (
        .i_data(write_image),
        .o_code(encoded_image),
        .i_code(raw_context[0+:CODE]),
        .o_data(decoded_image),
        .o_bad(image_bad),
        .o_corrected()
    );

    for (genvar c = 0; c < CD; c++) begin : g_context
        context_t record;
        assign record = contexts[c];
        assign o_context_valid[c] = run &&!context_bad[c] && record.valid;

        banked_scratchpad_state #(
            .WIDTH(CTX),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_state (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_data(context_next[c]),
            .o_data(contexts[c]),
            .o_bad(context_bad[c])
        );
    end

    banked_scratchpad_state #(
        .WIDTH($bits(control_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_control (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(n),
        .o_data(q),
        .o_bad(control_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(response_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_response (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(response_next),
        .o_data(response),
        .o_bad(response_bad)
    );

    banked_scratchpad_state #(
        .WIDTH(IM),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_active_image (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(active_next),
        .o_data(active_image),
        .o_bad(active_bad)
    );
endmodule
`default_nettype wire
