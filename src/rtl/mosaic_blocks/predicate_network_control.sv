`timescale 1ns / 1ps
`default_nettype none

// Prepare validates an isolated candidate; only quiescent commit installs it.
// Independent witnesses protect configuration, fault and dependency state.
module predicate_network_control #(
    parameter int N = 16,
    parameter int I = 5,
    parameter int O = 5,
    parameter int TX = 1,
    parameter int RX = 1,
    parameter int CI = 8,
    parameter int V = 16,
    parameter int K = 16,
    parameter int T = 8,
    parameter int PR = 8,
    parameter int EP = 2,
    parameter int P = 32,
    parameter int PM = 256,
    parameter int IL = 48,
    parameter int L = 48,
    parameter int LB = 48,
    parameter int LI = 6,
    parameter int LX = 6,
    parameter int NI = 4,
    parameter int S = 3,
    parameter int RES = 80,
    parameter int HW = 7,
    parameter int TW = 5,
    parameter int PW = 9,
    parameter int RI = 320,
    parameter int BODY = RI + LB + LB * PM + PW + CI + V + K + EP,
    parameter int SUPPORT_MULTICAST = 1,
    parameter int MAX_MULTICAST_FANOUT = 4,
    parameter int MAX_TREE_DESTINATIONS = 16,
    parameter int SUPPORT_SCHEDULE_CHECK = 1,
    parameter int SUPPORT_LINK_EXCLUSION = 1,
    parameter int CONTROL_PROTECTION = 0,
    parameter int ASYNC_RESET = 0,
    parameter int TOPOLOGY_ID = 0
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
    input wire i_boundary_isolate,
    input wire i_test_enable,
    input wire i_scan_enable,
    input wire i_schedule_pause,
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
    output wire o_boundary_isolated,
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
    output wire [7:0] o_cfg_prepare_error_code,
    output wire [CI-1:0] o_active_context_id,
    output wire [V-1:0] o_active_context_version,
    output wire [K-1:0] o_active_kernel_id,
    output wire [EP-1:0] o_active_epoch,
    output wire [LB-1:0] o_faulted_link_mask,
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
    input wire i_all_idle,
    input wire i_nodes_ready,
    input wire i_nodes_match,
    input wire i_integrity_bad,
    input wire [7:0] i_runtime_code,
    input wire [NI-1:0] i_runtime_node,
    input wire [LI-1:0] i_runtime_link,
    input wire [PR-1:0] i_runtime_source,
    input wire [T-1:0] i_runtime_tag,
    input wire [T-1:0] i_runtime_expected_tag,
    input wire [N*RX-1:0] i_alignment_event,
    input wire [N*O*I-1:0] i_connectivity,
    input wire [LB-1:0] i_link_present,
    input wire [RES*32-1:0] i_input_source,
    input wire [N*O*HW-1:0] i_output_target,
    input wire [RES*LX-1:0] i_input_links,
    input wire [N*O*LX-1:0] i_output_links,
    output wire [RI-1:0] o_route,
    output wire [LB-1:0] o_schedule_enable,
    output wire [LB*PM-1:0] o_slots,
    output wire [PW-1:0] o_period,
    output wire [RES*HW-1:0] o_depths,
    output wire [CI-1:0] o_install_context,
    output wire [N*RX-1:0] o_quarantine,
    output wire o_ingress,
    output wire o_transport,
    output wire o_install,
    output wire o_flush,
    output wire o_route_check,
    output wire [31:0] o_tick,
    output wire o_schedule_check,
    output wire o_configuration_busy
);
    import predicate_network_pkg::*;

    // Width-dependent records stay local. Payloads are unreset; the shared
    // protected validity witnesses establish when they are meaningful.
    typedef struct packed {
        logic [RES*HW-1:0] depths;
        logic [P-1:0] proof;
        logic [EP-1:0] epoch;
        logic [K-1:0] kernel;
        logic [V-1:0] version;
        logic [CI-1:0] context_id;
        logic [PW-1:0] period;
        logic [LB*PM-1:0] slots;
        logic [LB-1:0] schedule_enable;
        logic [RI-1:0] route;
    } image_t;

    typedef struct packed {
        phase_t phase;
        logic active;
        logic shadow_valid;
        logic [EP-1:0] epoch;
        logic [LB-1:0] faults;
        logic [N*RX-1:0] quarantine;
        logic flush_seen;
        logic flush_pending;
        logic flush_pulse;
        logic isolated;
        logic started;
        logic [31:0] tick;
        logic fatal;
        logic [7:0] error_code;
        logic [NI-1:0] error_node;
        logic [LI-1:0] error_link;
        logic [PR-1:0] error_source;
        logic [T-1:0] error_tag;
        logic [T-1:0] expected_tag;
        logic [CI-1:0] error_context;
        logic [V-1:0] error_version;
        logic [K-1:0] error_kernel;
        logic [EP-1:0] error_epoch;
        logic prepared;
        logic rejected;
        logic committed;
        logic aborted;
        logic [7:0] prepare_code;
    } control_t;

    typedef struct packed {
        logic [RES-1:0] done;
        logic [RES*TW-1:0] counts;
        logic [RES*HW-1:0] distance;
    } graph_t;

    control_t q;
    control_t n;
    image_t candidate;
    image_t candidate_next;
    image_t shadow;
    image_t shadow_next;
    image_t active;
    image_t active_next;
    graph_t graph;
    graph_t graph_next;
    wire [RES-1:0] done = graph.done;
    wire [RES*TW-1:0] counts = graph.counts;
    wire [RES*HW-1:0] distance = graph.distance;
    wire [LB-1:0] faults = q.faults;
    wire [RI-1:0] candidate_route = candidate.route;
    wire [LB-1:0] candidate_schedule = candidate.schedule_enable;
    wire [LB*PM-1:0] candidate_slots = candidate.slots;
    wire [RI-1:0] active_route = active.route;
    wire [LB-1:0] active_links = required_links(active_route);
    wire [LB-1:0] candidate_links = required_links(candidate_route);
    wire [RES-1:0] candidate_used = used_inputs(candidate_route);
    wire control_bad;
    wire candidate_bad;
    wire shadow_bad;
    wire active_bad;
    wire graph_bad;
    wire integrity_bad = control_bad || candidate_bad || shadow_bad || active_bad ||
        graph_bad || i_integrity_bad;
    wire run = i_reset_n === 1'b1;
    wire known_control = (^{i_enable, i_drain, i_flush, i_error_clear, i_cfg_prepare_valid,
        i_cfg_commit_valid, i_cfg_abort, i_link_fault_valid, i_boundary_isolate,
        i_test_enable, i_scan_enable, i_schedule_pause} !== 1'bx);
    wire operating = q.phase == PRED_PHASE_READY || q.phase == PRED_PHASE_CHECK ||
        q.phase == PRED_PHASE_DEPTH;
    wire empty = i_all_idle && q.phase == PRED_PHASE_READY &&!q.flush_pending;
    wire pause = i_schedule_pause === 1'b1 && i_all_idle &&
        (active.period != 0 && q.tick % 32'(active.period) == 0);
    wire prepare_fire = i_cfg_prepare_valid === 1'b1 && o_cfg_prepare_ready;
    wire commit_fire = i_cfg_commit_valid === 1'b1 && o_cfg_commit_ready;
    wire fault_fire = i_link_fault_valid === 1'b1 && o_link_fault_ready;
    wire known_image = (^{i_cfg_route_image, i_cfg_schedule_enable, i_cfg_schedule_period,
        i_cfg_schedule_slot_image, i_cfg_context_id, i_cfg_context_version, i_cfg_kernel_id,
        i_cfg_epoch, i_cfg_route_proof_id} !== 1'bx);
    logic [7:0] candidate_error;
    logic [RES-1:0] resolved;
    logic [RES*TW-1:0] resolved_counts;
    logic [RES*HW-1:0] resolved_distance;
    logic graph_limit;

    function automatic logic [RES-1:0] used_inputs(input logic [RI-1:0] route);
        logic [RES-1:0] used;
        int source;
        used = '0;

        for (int node = 0; node < N; node++) begin
            for (int o = 0; o < O; o++) begin
                source = int'(route[N*O+(node*O+o)*S+:S]);

                if (route[node*O+o] && source < I) used[node*I+source] = 1'b1;
            end
        end

        return used;
    endfunction

    function automatic logic [LB-1:0] required_links(input logic [RI-1:0] route);
        logic [LB-1:0] required;
        int source;
        int link_id;
        required = '0;

        for (int node = 0; node < N; node++) begin
            for (int o = 0; o < O; o++) begin
                if (route[node*O+o]) begin
                    source = int'(route[N*O+(node*O+o)*S+:S]);
                    link_id = int'(i_output_links[(node*O+o)*LX+:LX]);

                    if (link_id < L) required[link_id] = 1'b1;

                    if (source < I) begin
                        link_id = int'(i_input_links[(node*I+source)*LX+:LX]);

                        if (link_id < L) required[link_id] = 1'b1;
                    end
                end
            end
        end

        return required;
    endfunction

    function automatic logic [31:0] proof_hash(input logic [BODY-1:0] body);
        localparam int BYTES = (BODY + 32 + 7) / 8;
        logic [BYTES*8-1:0] bytes;
        logic [31:0] crc;
        bytes = (BYTES*8)'({body, 32'(TOPOLOGY_ID)});
        crc = 32'hffffffff;

        for (int b = 0; b < BYTES; b++) begin
            crc ^= {24'b0, bytes[b*8+:8]};

            for (int k = 0; k < 8; k++) crc = crc[0] ?
                (crc >> 1) ^ 32'h82f63b78 : crc >> 1;
        end

        return ~crc;
    endfunction

    wire [31:0] candidate_proof = proof_hash(candidate[BODY-1:0]);

    function automatic int provider_resource(input int resource);
        int port_index;
        int source;
        port_index = int'(i_input_source[resource*32+:32]);

        if (port_index >= N * O || !candidate_route[port_index]) return RES;

        source = int'(candidate_route[N*O+port_index*S+:S]);

        return source < I ? port_index / O * I + source : RES;

    endfunction

    function automatic int fault_node(input int link_id);
        // Internal links are attributed to their receiver. An outward boundary
        // link has no local receiver, so use its owning perimeter node.
        for (int u = 0; u < RES; u++)
            if (int'(i_input_links[u*LX+:LX]) == link_id) return u / I;

        for (int p = 0; p < N * O; p++)
            if (int'(i_output_links[p*LX+:LX]) == link_id) return p / O;

        return 0;
    endfunction

    wire candidate_schedule_bad;

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
        .i_route(candidate_route),
        .i_enable(candidate_schedule),
        .i_slots(candidate_slots),
        .i_period(candidate.period),
        .i_inputs(i_input_links),
        .i_outputs(i_output_links),
        .o_input_slots(),
        .o_checked(),
        .o_bad(candidate_schedule_bad)
    );

    // Validation uses the complete candidate. Rejection never writes the shadow.
    always @* begin
        candidate_error = PRED_NET_OK;

        if (candidate.proof == 0 || candidate.proof != P'(candidate_proof))
            candidate_error = PRED_NET_ERR_PROOF;
        else if (candidate.version == 0 ||
            (q.active && candidate.context_id == active.context_id &&
                candidate.version <= active.version) ||
            (q.shadow_valid && candidate.context_id == shadow.context_id &&
                candidate.version <= shadow.version)) candidate_error = PRED_NET_ERR_VERSION;
        else if (candidate.period == 0 || candidate.period > PM || candidate_schedule_bad)
            candidate_error = PRED_NET_ERR_SCHEDULE;
        else if ((candidate_links & ~i_link_present) != 0 ||
            (candidate_schedule & ~candidate_links) != 0) candidate_error = PRED_NET_ERR_ROUTE;
        else if (SUPPORT_LINK_EXCLUSION && (candidate_links & faults) != 0)
            candidate_error = PRED_NET_ERR_FAULT;
        else if ((SUPPORT_SCHEDULE_CHECK == 0 && candidate_schedule != 0) ||
            (candidate_schedule != 0 && candidate_schedule != candidate_links))
            candidate_error = PRED_NET_ERR_SCHEDULE;

        for (int l = 0; l < LB; l++) begin
            if ((!candidate_schedule[l] && candidate_slots[l*PM+:PM] != 0) ||
                (candidate_schedule[l] && (candidate_slots[l*PM+:PM] == 0 ||
                    (candidate_slots[l*PM+:PM] >> candidate.period) != 0)))
                candidate_error = PRED_NET_ERR_SCHEDULE;
        end

        for (int node = 0; node < N; node++) begin
            for (int o = 0; o < O; o++) begin
                int source;
                int target;
                int fanout;
                source = int'(candidate_route[N*O+(node*O+o)*S+:S]);
                target = int'(i_output_target[(node*O+o)*HW+:HW]);
                fanout = 0;

                for (int other = 0; other < O; other++)
                    if (candidate_route[node*O+other] &&
                        candidate_route[N*O+(node*O+other)*S+:S] == S'(source)) fanout++;

                if (candidate_error == PRED_NET_OK && candidate_route[node*O+o]) begin
                    if (source >= I || !i_connectivity[node*O*I+o*I+source])
                        candidate_error = PRED_NET_ERR_ROUTE;
                    else if (fanout > MAX_MULTICAST_FANOUT ||
                        (!SUPPORT_MULTICAST && fanout > 1)) candidate_error = PRED_NET_ERR_FANOUT;
                    else if (target < RES && !candidate_used[target])
                        candidate_error = PRED_NET_ERR_DEPENDENCY;
                    else if (source >= TX) begin
                        int provider;
                        provider = provider_resource(node * I + source);

                        if (int'(i_input_links[(node*I+source)*LX+:LX]) < IL &&
                            (provider == RES || !candidate_used[provider]))
                            candidate_error = PRED_NET_ERR_DEPENDENCY;
                    end
                end
            end
        end
    end

    // Parallel leaf elimination proves a forest and counts every terminal copy.
    // A physical input has exactly one provider, so paths cannot reconverge.
    // A forward pass then certifies startup latency for schedule checking.
    always @* begin
        resolved = done;
        resolved_counts = counts;
        resolved_distance = distance;
        graph_limit = 1'b0;

        if (q.phase == PRED_PHASE_CHECK || q.phase == PRED_PHASE_DEPTH) begin
            for (int u = 0; u < RES; u++) begin
                if (!candidate_used[u]) resolved[u] = 1'b1;
                else if (!done[u]) begin
                    if (q.phase == PRED_PHASE_CHECK) begin
                        logic children_ready;
                        int total;
                        children_ready = 1'b1;
                        total = 0;

                        for (int o = 0; o < O; o++) begin
                            int target;
                            target = int'(i_output_target[(u/I*O+o)*HW+:HW]);

                            if (candidate_route[u/I*O+o] &&
                                candidate_route[N*O+(u/I*O+o)*S+:S] == S'(u % I)) begin

                                if (target < RES) begin
                                    children_ready &= done[target];
                                    total += int'(counts[target*TW+:TW]);
                                end else total++;
                            end
                        end

                        if (children_ready) begin
                            resolved[u] = 1'b1;
                            resolved_counts[u*TW+:TW] = TW'(total);

                            if (total > MAX_TREE_DESTINATIONS) graph_limit = 1'b1;
                        end
                    end else begin
                        int parent;
                        int link_id;
                        parent = provider_resource(u);
                        link_id = int'(i_input_links[u*LX+:LX]);

                        if (parent == RES) begin
                            resolved[u] = 1'b1;
                            resolved_distance[u*HW+:HW] = HW'(u%I < TX ? 0 : 1);
                        end else if (done[parent]) begin
                            resolved[u] = 1'b1;
                            resolved_distance[u*HW+:HW] = distance[parent*HW+:HW] + 1'b1;
                        end
                    end
                end
            end
        end
    end

    assign o_route = active.route;
    assign o_schedule_enable = active.schedule_enable;
    assign o_slots = active.slots;
    assign o_period = active.period;
    assign o_depths = active.depths;
    assign o_install_context = active.context_id;
    assign o_route_check = run && q.active &&!control_bad &&!active_bad && operating;
    assign o_active_context_valid = o_route_check &&!integrity_bad &&!q.fatal;
    assign o_active_context_id = o_active_context_valid ? active.context_id : '0;
    assign o_active_context_version = o_active_context_valid ? active.version : '0;
    assign o_active_kernel_id = o_active_context_valid ? active.kernel : '0;
    assign o_active_epoch = run &&!control_bad ? q.epoch : '0;
    assign o_shadow_valid = run &&!integrity_bad && q.shadow_valid;
    assign o_faulted_link_mask = run &&!control_bad ? faults : '0;
    assign o_quarantine = q.quarantine;
    assign o_active_link_fault = run &&!control_bad &&!active_bad && q.active &&
        (|(active_links & faults));
    assign o_error = run && (integrity_bad || q.error_code != PRED_NET_OK);
    assign o_error_code = !run ? PRED_NET_OK :
        integrity_bad ? PRED_NET_ERR_INTEGRITY : q.error_code;
    assign o_error_node = !control_bad ? q.error_node : '0;
    assign o_error_link = !control_bad ? q.error_link : '0;
    assign o_error_source = !control_bad ? q.error_source : '0;
    assign o_error_tag = !control_bad ? q.error_tag : '0;
    assign o_error_expected_tag = !control_bad ? q.expected_tag : '0;
    assign o_error_context_id = !control_bad ? q.error_context : '0;
    assign o_error_context_version = !control_bad ? q.error_version : '0;
    assign o_error_kernel_id = !control_bad ? q.error_kernel : '0;
    assign o_error_epoch = !control_bad ? q.error_epoch : '0;
    assign o_transport = run && known_control && operating &&!integrity_bad &&!q.fatal &&
        i_flush === 1'b0 &&!q.flush_pending;
    assign o_ingress = o_transport && q.active && q.error_code == PRED_NET_OK &&
        !o_active_link_fault && i_enable === 1'b1 && i_drain === 1'b0 &&
        i_boundary_isolate === 1'b0 &&!q.isolated && i_link_fault_valid === 1'b0 &&
        i_cfg_commit_valid === 1'b0;
    assign o_flush = run && i_flush === 1'b1;
    assign o_quiescent = run && known_control && empty &&!integrity_bad && i_flush === 1'b0;
    assign o_drained = o_quiescent && i_drain === 1'b1;
    assign o_flush_completed = run &&!control_bad && q.flush_pulse;
    assign o_boundary_isolated = run &&!control_bad && q.isolated;
    assign o_cfg_prepare_ready = run && known_control && q.phase == PRED_PHASE_READY &&
        !integrity_bad &&!q.fatal &&!q.flush_pending && i_flush === 1'b0 &&
        i_cfg_abort === 1'b0 && i_cfg_commit_valid === 1'b0 && i_link_fault_valid === 1'b0;
    assign o_cfg_commit_ready = o_quiescent && q.shadow_valid &&!q.fatal &&
        i_cfg_abort === 1'b0 && i_cfg_prepare_valid === 1'b0 && i_link_fault_valid === 1'b0 &&
        i_cfg_commit_context_id === shadow.context_id &&
        i_cfg_commit_context_version === shadow.version &&
        (required_links(shadow.route) & faults) == 0;
    assign o_link_fault_ready = SUPPORT_LINK_EXCLUSION && run && known_control &&
        q.phase == PRED_PHASE_READY &&!integrity_bad &&!q.flush_pending && i_flush === 1'b0 &&
        i_cfg_abort === 1'b0 && i_cfg_prepare_valid === 1'b0 && i_cfg_commit_valid === 1'b0 &&
        (^i_link_fault_mask !== 1'bx) && (i_link_fault_mask & ~i_link_present) == 0 &&
        (i_all_idle || (faults & ~i_link_fault_mask) == 0);
    assign o_install = run && known_control && q.phase == PRED_PHASE_INSTALL &&
        !integrity_bad && i_flush === 1'b0 &&!q.flush_pending;
    assign o_cfg_prepared = run &&!control_bad && q.prepared;
    assign o_cfg_prepare_rejected = run &&!control_bad && q.rejected;
    assign o_cfg_committed = run &&!control_bad && q.committed;
    assign o_cfg_aborted = run &&!control_bad && q.aborted;
    assign o_cfg_prepare_error_code = !control_bad ? q.prepare_code : PRED_NET_ERR_INTEGRITY;
    assign o_tick = q.tick;
    assign o_schedule_check = SUPPORT_SCHEDULE_CHECK && o_transport && q.active &&
        (|active.schedule_enable) && (q.started || i_enable === 1'b1) &&!pause &&
        i_error_clear === 1'b0;
    assign o_configuration_busy = run && q.phase != PRED_PHASE_READY;

    always @* begin
        n = q;
        candidate_next = candidate;
        shadow_next = shadow;
        active_next = active;
        graph_next = graph;
        n.prepared = 1'b0;
        n.rejected = 1'b0;
        n.committed = 1'b0;
        n.aborted = 1'b0;
        n.flush_pulse = 1'b0;

        if (run && known_control &&!q.flush_pending && i_flush === 1'b0) begin
            if (q.phase == PRED_PHASE_CHECK || q.phase == PRED_PHASE_DEPTH) begin
                graph_next.done = resolved;
                graph_next.counts = resolved_counts;
                graph_next.distance = resolved_distance;

                if (candidate_error != PRED_NET_OK || graph_limit ||
                    (resolved == done &&!(&resolved))) begin
                    n.phase = PRED_PHASE_READY;
                    n.rejected = 1'b1;
                    n.prepare_code = candidate_error != PRED_NET_OK ? candidate_error :
                        graph_limit ? PRED_NET_ERR_TREE : PRED_NET_ERR_DEPENDENCY;
                end else if (&resolved) begin
                    if (q.phase == PRED_PHASE_CHECK) begin
                        n.phase = PRED_PHASE_DEPTH;
                        graph_next.done = '0;
                    end else begin
                        shadow_next = candidate;
                        shadow_next.depths = resolved_distance;
                        n.shadow_valid = 1'b1;
                        n.phase = PRED_PHASE_READY;
                        n.prepared = 1'b1;
                        n.prepare_code = PRED_NET_OK;
                    end
                end
            end

            if (q.phase == PRED_PHASE_INSTALL && i_nodes_ready) n.phase = PRED_PHASE_ACK;

            if (q.phase == PRED_PHASE_ACK) begin
                n.phase = PRED_PHASE_READY;
                n.committed = i_nodes_match;
                n.tick = '0;
                n.started = 1'b0;

                if (!i_nodes_match) begin
                    n.error_code = PRED_NET_ERR_INTEGRITY;
                    n.fatal = 1'b1;
                end
            end

            if (prepare_fire) begin
                n.prepare_code = PRED_NET_OK;

                if (!known_image) begin
                    n.rejected = 1'b1;
                    n.prepare_code = PRED_NET_ERR_UNKNOWN;
                end else begin
                    candidate_next = '0;
                    candidate_next.route = i_cfg_route_image;
                    candidate_next.schedule_enable = i_cfg_schedule_enable;
                    candidate_next.slots = i_cfg_schedule_slot_image;
                    candidate_next.period = i_cfg_schedule_period;
                    candidate_next.context_id = i_cfg_context_id;
                    candidate_next.version = i_cfg_context_version;
                    candidate_next.kernel = i_cfg_kernel_id;
                    candidate_next.epoch = i_cfg_epoch;
                    candidate_next.proof = i_cfg_route_proof_id;
                    graph_next = '0;
                    n.phase = PRED_PHASE_CHECK;
                end
            end

            // Abort may cancel validation, but a consumed commit owns its image.
            if (i_cfg_abort === 1'b1 && operating &&
                (q.shadow_valid || q.phase != PRED_PHASE_READY)) begin
                n.shadow_valid = 1'b0;
                n.phase = PRED_PHASE_READY;
                n.aborted = 1'b1;
            end

            if (commit_fire) begin
                active_next = shadow;
                n.active = 1'b1;
                n.shadow_valid = 1'b0;
                n.epoch = shadow.epoch;
                n.phase = PRED_PHASE_INSTALL;
                n.tick = '0;
                n.started = 1'b0;
            end

            if (fault_fire) n.faults = i_link_fault_mask;

            if (i_boundary_isolate === 1'b0) n.isolated = 1'b0;
            else if (empty) n.isolated = 1'b1;

            n.quarantine = q.quarantine | i_alignment_event;

            if (o_schedule_check) begin
                n.started = 1'b1;
                n.tick = q.tick + 1'b1;

                // Past startup, rebasing by a whole period preserves slots and
                // prevents phase wrap from creating a new startup interval.
                if (q.tick > 32'(RES + PM + 4)) n.tick =
                    q.tick + 1'b1 - 32'(active.period);
            end
        end

        if (run && i_flush === 1'b0) n.flush_seen = 1'b0;

        if (run && i_flush === 1'b1 &&!q.flush_seen) begin
            n.flush_seen = 1'b1;
            n.flush_pending = 1'b1;
            n.epoch = q.epoch + 1'b1;
            n.started = 1'b0;
            n.tick = '0;
            n.quarantine = '0;
        end

        if (run && q.flush_pending && i_all_idle) begin
            n.flush_pending = 1'b0;
            n.flush_pulse = 1'b1;
        end

        if (o_quiescent && i_error_clear === 1'b1 &&!integrity_bad &&!q.fatal &&
            !o_active_link_fault && i_runtime_code == PRED_NET_OK && known_control) begin
            n.error_code = PRED_NET_OK;
            n.error_node = '0;
            n.error_link = '0;
            n.error_source = '0;
            n.error_tag = '0;
            n.expected_tag = '0;
            n.started = 1'b0;
            n.tick = '0;
        end

        if (run && (integrity_bad || !known_control || i_runtime_code != PRED_NET_OK ||
            o_active_link_fault)) begin

            if (q.error_code == PRED_NET_OK) begin
                n.error_code = integrity_bad ? PRED_NET_ERR_INTEGRITY :
                    !known_control ? PRED_NET_ERR_UNKNOWN : o_active_link_fault ?
                        PRED_NET_ERR_FAULT : i_runtime_code;
                n.error_node = i_runtime_node;
                n.error_link = i_runtime_link;
                n.error_source = i_runtime_source;
                n.error_tag = i_runtime_tag;
                n.expected_tag = i_runtime_expected_tag;
                n.error_context = !active_bad ? active.context_id : '0;
                n.error_version = !active_bad ? active.version : '0;
                n.error_kernel = !active_bad ? active.kernel : '0;
                n.error_epoch = !control_bad ? q.epoch : '0;

                if (o_active_link_fault) begin
                    for (int l = L - 1; l >= 0; l--) begin
                        if (active_links[l] && faults[l]) begin
                            n.error_link = LI'(l);
                            n.error_node = NI'(fault_node(l));
                        end
                    end
                end
            end

            if (integrity_bad) n.fatal = 1'b1;
        end
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
        .WIDTH($bits(image_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_candidate (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(candidate_next),
        .o_data(candidate),
        .o_bad(candidate_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(image_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_shadow (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(shadow_next),
        .o_data(shadow),
        .o_bad(shadow_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(image_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_active (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(active_next),
        .o_data(active),
        .o_bad(active_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(graph_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_graph (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(graph_next),
        .o_data(graph),
        .o_bad(graph_bad)
    );
endmodule
`default_nettype wire
