`timescale 1ns / 1ps
`default_nettype none
module cpt_body #(
    parameter TILE_ID = 0,
    parameter DATA_METADATA_WIDTH = 128,
    parameter DATA_INPUT_PORTS = 2,
    parameter DATA_OUTPUT_PORTS = 1,
    parameter PREDICATE_WIDTH = 8,
    parameter PREDICATE_METADATA_WIDTH = 64,
    parameter PREDICATE_INPUT_PORTS = 2,
    parameter PREDICATE_OUTPUT_PORTS = 2,
    parameter EVENT_WIDTH = 256,
    parameter EVENT_INPUT_PORTS = 1,
    parameter EVENT_OUTPUT_PORTS = 1,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    parameter PREDICATE_LANES = 8,
    parameter PREDICATE_DEPTH = 8,
    parameter EVENT_RECORD_WIDTH = 256,
    parameter CONTROL_WIDTH = 32,
    parameter CONTROL_REGISTER_DEPTH = 8,
    parameter FU_PROFILE = 1,
    // Explicit enables override the legacy profile without coupling peer FUs.
    parameter ENABLE_PREDICATE = 1,
    parameter ENABLE_LOOP_CONTROLLER = 1,
    parameter ENABLE_EVENT_BARRIER = 1,
    parameter ENABLE_ACTIONS = FU_PROFILE >= 1,
    parameter MAX_LOOP_DEPTH = 4,
    parameter INDEX_WIDTH = 32,
    parameter TRIP_COUNT_WIDTH = 32,
    parameter LINEAR_COUNT_WIDTH = 64,
    parameter LOOP_II_WIDTH = 8,
    parameter LOOP_EXPORT_LEVELS = 1,
    parameter NUM_EVENTS = 16,
    parameter EVENT_COUNT_WIDTH = 4,
    parameter NUM_EVENT_NAMESPACES = 1,
    parameter MAX_EVENT_SOURCES = 16,
    parameter EVENT_INPUT_FIFO_DEPTH = 8,
    parameter EVENT_OUTPUT_FIFO_DEPTH = 8,
    parameter NUM_WAIT_SLOTS = 4,
    parameter WAIT_RESULT_QUEUE_DEPTH = 4,
    parameter NUM_BARRIERS = 4,
    parameter MAX_PARTICIPANTS = 16,
    parameter BARRIER_RELEASE_QUEUE_DEPTH = 4,
    parameter BARRIER_GENERATION_WIDTH = 4,
    parameter ACTION_QUEUE_DEPTH = 8,
    parameter ACTION_RESPONSE_DEPTH = 8,
    parameter MAX_OUTSTANDING_ACTIONS = 4,
    parameter ACTION_TAG_WIDTH = 8,
    parameter EVENT_SEQUENCE_WIDTH = 16,
    parameter TIMEOUT_COUNTER_WIDTH = 32,
    parameter MAX_PRIORITY_BURST = 8,
    parameter SUPPORT_CONTEXT_COORDINATION = 1,
    parameter SUPPORT_CLUSTER_LIFECYCLE = 1,
    parameter SUPPORT_TIMEOUT = 1,
    parameter SUPPORT_CHECKPOINT = 0,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter REQUIRE_CANONICAL_FORMAT = 1,
    parameter PREDICATE_PROTECTION = 0,
    parameter EVENT_PROTECTION = 0,
    parameter CONFIG_WORD_COUNT = 17,
    parameter DATA_WIDTH = 64,
    localparam int D = DATA_WIDTH,
    localparam int M = DATA_METADATA_WIDTH,
    localparam int NI = DATA_INPUT_PORTS,
    localparam int NO = DATA_OUTPUT_PORTS,
    localparam int C = CONTEXT_DEPTH,
    localparam int W = CONFIG_DATA_WIDTH,
    localparam int N = CONFIG_WORD_COUNT,
    localparam int IM = W * N,
    localparam int V = CONTEXT_VERSION_WIDTH,
    localparam int PM = PREDICATE_METADATA_WIDTH,
    localparam int O = OWNER_ID_WIDTH,
    localparam int K = KERNEL_ID_WIDTH,
    localparam int PI = PREDICATE_INPUT_PORTS,
    localparam int P = PREDICATE_WIDTH,
    localparam int PO = PREDICATE_OUTPUT_PORTS,
    localparam int EI = 1,
    localparam int E = EVENT_WIDTH,
    localparam int EO = 1,
    localparam int S = 8,
    localparam int ER = 8,
    localparam int CI = C > 1 ? $clog2(C) : 1
) (
    input logic i_loop_delivered,
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic [3:0] i_execution_state,
    input logic [OWNER_ID_WIDTH-1:0] i_owner,
    input logic [KERNEL_ID_WIDTH-1:0] i_kernel,
    input logic i_isolate,
    input logic i_monitor_enable,
    input logic [2:0] i_power_state,
    input logic [4:0] i_counter_index,
    output wire [31:0] o_counter_data,
    output wire o_counter_available,
    output wire o_advance_valid,
    input logic i_advance_ready,
    output wire [CI-1:0] o_advance_context,
    input logic [CI-1:0] o_body_context_id,
    input logic [V-1:0] o_body_context_version,
    input logic [IM-1:0] o_body_context_image,
    input logic [N-1:0] o_body_context_word_valid,
    input logic o_body_context_active,
    input logic o_body_validate_valid,
    output wire i_body_validate_ready,
    input logic [CI-1:0] o_body_validate_context_id,
    input logic [V-1:0] o_body_validate_context_version,
    input logic [IM-1:0] o_body_validate_context_image,
    input logic [N-1:0] o_body_validate_word_valid,
    output wire i_body_validate_result_valid,
    input logic o_body_validate_result_ready,
    output wire [CI-1:0] i_body_validate_context_id,
    output wire [V-1:0] i_body_validate_context_version,
    output wire i_body_validate_legal,
    output wire [ER-1:0] i_body_validate_error_code,
    input logic o_body_start,
    input logic o_body_suspend_request,
    input logic o_body_resume,
    input logic o_body_drain_request,
    input logic o_body_flush,
    input logic [NI-1:0] o_body_data_in_valid,
    output wire [NI-1:0] i_body_data_in_ready,
    input logic [NI*D-1:0] o_body_data_in_payload,
    input logic [NI*M-1:0] o_body_data_in_metadata,
    input logic [PI-1:0] o_body_predicate_in_valid,
    output wire [PI-1:0] i_body_predicate_in_ready,
    input logic [PI*P-1:0] o_body_predicate_in_payload,
    input logic [PI*PM-1:0] o_body_predicate_in_metadata,
    input logic [EI-1:0] o_body_event_in_valid,
    output wire [EI-1:0] i_body_event_in_ready,
    input logic [E*EI-1:0] o_body_event_in_payload,
    output wire [NO-1:0] i_body_data_out_valid,
    input logic [NO-1:0] o_body_data_out_ready,
    output wire [NO*D-1:0] i_body_data_out_payload,
    output wire [NO*M-1:0] i_body_data_out_metadata,
    output wire [PO-1:0] i_body_predicate_out_valid,
    input logic [PO-1:0] o_body_predicate_out_ready,
    output wire [PO*P-1:0] i_body_predicate_out_payload,
    output wire [PO*PM-1:0] i_body_predicate_out_metadata,
    output wire [EO-1:0] i_body_event_out_valid,
    input logic [EO-1:0] o_body_event_out_ready,
    output wire [E*EO-1:0] i_body_event_out_payload,
    output wire i_body_busy,
    output wire i_body_idle,
    output wire i_body_safe_point,
    output wire i_body_drain_done,
    output wire i_body_completed,
    output wire [S-1:0] i_body_stall_reasons,
    output wire i_body_error,
    output wire i_body_fatal_error,
    output wire [ER-1:0] i_body_error_code,
    output wire i_body_wakeup_required
);
    import cpt_pkg::*;
    import tile_shell_pkg::*;
    localparam int EI_BITS = NUM_EVENTS > 1 ? $clog2(NUM_EVENTS) : 1;
    localparam int WI_BITS = NUM_WAIT_SLOTS > 1 ? $clog2(NUM_WAIT_SLOTS) : 1;
    localparam int BI_BITS = NUM_BARRIERS > 1 ? $clog2(NUM_BARRIERS) : 1;
    localparam int PA_BITS = MAX_PARTICIPANTS > 1 ? $clog2(MAX_PARTICIPANTS) : 1;
    localparam int PR_BITS = PREDICATE_DEPTH > 1 ? $clog2(PREDICATE_DEPTH) : 1;
    localparam int RF_BITS = $clog2(CONTROL_REGISTER_DEPTH);
    localparam int LOOP_BITS = 3 * INDEX_WIDTH + TRIP_COUNT_WIDTH + 5;
    localparam int LD = MAX_LOOP_DEPTH;
    localparam int IW = INDEX_WIDTH;
    localparam int TW = TRIP_COUNT_WIDTH;
    localparam int DEPTH_BITS = $clog2(LD + 1);

    wire known_reset = i_rstb === 1'b1;
    wire enable = known_reset && i_clock_enable === 1'b1 && i_isolate === 1'b0;
    wire live = enable && o_body_context_active === 1'b1;
    wire running = live && (i_execution_state >= TILE_ACTIVE &&
        i_execution_state <= TILE_SYNC_STALL || i_execution_state == TILE_DRAINING);
    wire flush = o_body_flush === 1'b1;
    wire reset_b = i_rstb !== 1'b0 &&!flush;
    wire [IM-1:0] image = o_body_context_image;
    wire [15:0] epoch = image[80+:16];
    wire [3:0] configured_class = image[16+:4];
    wire [15:0] configured_mask = image[32+:16];
    wire [PO-1:0] predicate_route = PO'(image[48+:16]);
    wire [NUM_EVENTS-1:0] event_enable = NUM_EVENTS'(image[64+:16]);
    wire [31:0] timeout = image[96+:32];
    wire [15:0] targets = image[128+:16];
    wire [15:0] package_version = image[144+:16];
    wire [15:0] route_version = image[160+:16];
    wire [7:0] loop_depth = image[176+:8];
    wire [7:0] loop_ii = image[184+:8];
    wire [LD-1:0] loop_export = LD'(image[192+:8]);
    wire [EI_BITS-1:0] loop_event = EI_BITS'(image[200+:8]);
    wire [31:0] command_limit = image[208+:32];
    wire sequence_enable = image[240];
    wire [CI-1:0] next_context = CI'(image[248+:8]);
    wire terminal_context = image[241];
    wire [7:0] allowed_classes = image[256+:8];
    wire [7:0] required_type = image[264+:8];

    logic validation_pending;
    logic [CI-1:0] validation_id;
    logic [V-1:0] validation_version;
    logic validation_legal;

    function automatic logic loop_compare(
        input logic signed [127:0] value,
        input logic signed [127:0] bound,
        input logic [2:0] comparison
    );
        case (comparison)
            0: return value < bound;
            1: return value <= bound;
            2: return value > bound;
            3: return value >= bound;
            default: return 1'b0;
        endcase
    endfunction

    // Validate immutable loop arithmetic before the shell can activate a package.
    // The native controller repeats its own checks when installing that package.
    function automatic logic legal_loop_image(input logic [IM-1:0] value);
        logic legal;
        logic zero_trip;
        logic [127:0] product_value;
        logic signed [127:0] first_value;
        logic signed [127:0] bound_value;
        logic signed [127:0] step_value;
        logic signed [127:0] last_value;
        logic signed [127:0] post_value;
        logic [TW-1:0] trips;
        logic [1:0] mode;
        logic [2:0] comparison;
        legal = 1'b1;
        zero_trip = 1'b0;
        product_value = 128'd1;

        for (int level = 0; level < LD; level++) begin
            if (level < value[176+:8] &&
                value[512+level*LOOP_BITS+3*IW+:TW] == 0) zero_trip = 1'b1;
        end

        for (int level = 0; level < LD; level++) begin
            first_value = $signed(value[512+level*LOOP_BITS+:IW]);
            bound_value = $signed(value[512+level*LOOP_BITS+IW+:IW]);
            step_value = $signed(value[512+level*LOOP_BITS+2*IW+:IW]);
            trips = value[512+level*LOOP_BITS+3*IW+:TW];
            mode = value[512+level*LOOP_BITS+3*IW+TW+:2];
            comparison = value[512+level*LOOP_BITS+3*IW+TW+2+:3];
            last_value = first_value + (128'({1'b0, trips}) - 1) * step_value;
            post_value = first_value + 128'({1'b0, trips}) * step_value;

            if (level >= value[176+:8]) begin
                legal = legal && value[512+level*LOOP_BITS+:LOOP_BITS] == 0;
            end else begin
                legal = legal && mode <= 1 && comparison <= 3;

                if (trips != 0) legal = legal && step_value != 0 &&
                    last_value == 128'($signed(last_value[IW-1:0]));

                if (mode == 1) begin
                    if (trips == 0)
                        legal = legal &&!loop_compare(first_value, bound_value, comparison);
                    else legal = legal && loop_compare(first_value, bound_value, comparison) &&
                        loop_compare(last_value, bound_value, comparison) &&
                        !loop_compare(post_value, bound_value, comparison) &&
                        (comparison <= 1 ? step_value > 0 : step_value < 0);
                end

                if (!zero_trip) begin
                    product_value = product_value * trips;
                    legal = legal && product_value[127:64] == 0;
                end
            end
        end

        return legal;
    endfunction

    function automatic logic legal_image(input logic [IM-1:0] value);
        logic legal;
        logic [15:0] mask;
        legal = ^value !== 1'bx && value[15:0] == 16'hc701 &&
            value[19:16] <= CPT_CMD_DISPATCH && value[31:20] == 0 &&
            value[79:64] != 0 && value[95:80] != 0 &&
            value[183:176] >= 1 && value[183:176] <= LD && value[191:184] != 0 &&
            value[199:192] != 0 && value[207:200] < NUM_EVENTS &&
            value[247:242] == 0 && value[255:248] < C && value[263:256] != 0 &&
            value[271:264] <= 6 && value[511:272] == 0 && legal_loop_image(value) &&
            (value[199:192] >> value[183:176]) == 0;
        mask = value[47:32];
        legal = legal && (mask >> P) == 0 && (value[63:48] >> PO) == 0 &&
            (value[79:64] >> NUM_EVENTS) == 0 &&
            (value[199:192] >> LD) == 0 && $countones(value[199:192]) <= LOOP_EXPORT_LEVELS;

        case (value[19:16])
            CPT_CMD_PREDICATE, CPT_CMD_COMPARE: legal &= ENABLE_PREDICATE;
            CPT_CMD_LOOP_CONFIG, CPT_CMD_LOOP_CONTROL: legal &= ENABLE_LOOP_CONTROLLER;
            CPT_CMD_EVENT, CPT_CMD_BARRIER: legal &= ENABLE_EVENT_BARRIER;
            CPT_CMD_ACTION: legal &= ENABLE_ACTIONS;
            default: begin end
        endcase

        if (!ENABLE_ACTIONS)
            legal = legal &&!value[262] && value[127:96] == 0;

        if (!SUPPORT_TIMEOUT) legal = legal && value[127:96] == 0;

        if (REQUIRE_CANONICAL_FORMAT && IM > 512 + LD * LOOP_BITS)
            legal = legal && (value >> (512 + LD * LOOP_BITS)) == 0;

        return legal;
    endfunction

    assign i_body_validate_ready = known_reset &&!validation_pending;
    assign i_body_validate_result_valid = known_reset && validation_pending;
    assign i_body_validate_context_id = validation_id;
    assign i_body_validate_context_version = validation_version;
    assign i_body_validate_legal = validation_legal;
    assign i_body_validate_error_code = validation_legal ? 8'd0 : 8'h80;

    always_ff @(posedge i_clk) begin
        if (i_rstb === 1'b0 || flush) validation_pending <= 1'b0;
        else if (known_reset) begin
            if (validation_pending && o_body_validate_result_ready === 1'b1)
                validation_pending <= 1'b0;
            if (o_body_validate_valid === 1'b1 && i_body_validate_ready) begin
                validation_pending <= 1'b1;
                validation_id <= o_body_validate_context_id;
                validation_version <= o_body_validate_context_version;
                validation_legal <= legal_image(o_body_validate_context_image) &&
                    o_body_validate_word_valid === {N{1'b1}};
            end
        end
    end

    cpt_engine_state_t phase;
    logic initialized;
    logic event_initialized;
    logic event_init_sent;
    logic loop_init_sent;
    logic loop_initialized;
    logic [CI-1:0] active_context;
    logic [V-1:0] active_version;
    logic started;
    logic [31:0] committed_count;
    logic completed;
    logic fatal;
    wire eb_fatal;
    wire loop_fatal;
    wire egress_fatal;
    wire event_input_fatal;
    wire command_admit;
    logic command_legal;
    wire ingress_ready;
    logic loop_frame_active;
    wire fatal_now = fatal || eb_fatal || loop_fatal || egress_fatal || event_input_fatal;
    wire context_change = live && (active_context != o_body_context_id ||
        active_version != o_body_context_version ||!initialized);
    wire private_flush = flush || context_change;
    wire unit_rstb = flush || context_change ? 1'b0 : i_rstb;
    wire storage_rstb = reset_b &&!context_change;
    // Context changes are allowed only after every prior obligation retires.
    logic [63:0] command_data;
    logic [127:0] command_meta;
    logic [P-1:0] command_predicate;
    logic command_condition;
    logic command_association_legal;
    logic suppressed;
    logic [3:0] command_class;
    wire [3:0] opcode = command_meta[36+:4];
    wire [3:0] source_a = command_meta[40+:4];
    wire [3:0] source_b = command_meta[44+:4];
    wire [3:0] destination = command_meta[48+:4];
    wire write_enable = command_meta[52];
    wire signed_compare = command_meta[53];
    wire false_token = command_meta[55];
    wire [15:0] mask = command_meta[64+:16];
    wire [7:0] object_id = command_meta[80+:8];
    wire [7:0] sub_id = command_meta[88+:8];
    wire [7:0] tag = command_meta[96+:8];
    wire [3:0] generation = command_meta[104+:4];
    wire [7:0] participant = command_meta[108+:8];
    wire [3:0] register_type = command_meta[116+:4];
    wire command_terminal = command_meta[120];
    wire [31:0] operand_a = command_data[31:0];
    wire [31:0] operand_b = command_data[63:32];
    logic [63:0] result;
    logic result_error;
    logic [P-1:0] result_predicate;
    logic [P-1:0] result_valid_lanes;
    logic [PO-1:0] pending_predicate;
    logic pending_data;
    logic pending_event;
    cpt_record_t command_record;
    wire need_external_predicate = o_body_data_in_metadata[54];
    wire inputs_known = ^{o_body_data_in_metadata[127:0],
        o_body_data_in_payload[63:0]} !== 1'bx;
    wire select_predicate = o_body_data_in_metadata[61];
    wire available_predicate = !need_external_predicate ||
        select_predicate >= PI || o_body_predicate_in_valid[select_predicate] === 1'b1;
    wire joined_valid;
    wire [1:0] joined_required = {o_body_data_in_metadata[60], 1'b1};
    wire auxiliary_known = !joined_required[1] ||
        ^{o_body_data_in_payload[64+:64], o_body_data_in_metadata[128+:128]} !== 1'bx;

    stream_join #(.NUM_INPUTS(2), .DATA_WIDTH(1), .HAS_REQUIRED_MASK(1)) u_command_join (
        .i_valid(o_body_data_in_valid),
        .o_ready(i_body_data_in_ready),
        .i_data(2'd0),
        .i_required(joined_required),
        .o_valid(joined_valid),
        .i_ready(command_admit)
    );

    assign command_admit = running && started &&!o_body_start &&!fatal_now &&!completed
            && initialized && event_initialized && loop_initialized &&!context_change &&
            phase == CPT_IDLE && available_predicate &&
        inputs_known && auxiliary_known && (!need_external_predicate ||
        select_predicate >= PI ||
        ^{o_body_predicate_in_payload[select_predicate*P+:P],
            o_body_predicate_in_metadata[select_predicate*PM+:PM]} !== 1'bx);
    wire issue = command_admit && joined_valid === 1'b1;
    assign i_body_predicate_in_ready = issue && need_external_predicate &&
        select_predicate < PI ? PI'(1) << select_predicate : '0;
    wire execute = enable && phase == CPT_EXECUTE &&!fatal_now;
    wire effects = execute && command_condition && command_legal;
    wire retire = enable && phase == CPT_RETIRE &&!pending_data &&
        pending_predicate == 0 &&!pending_event;

    // Native predicate storage plus allocation/version tags. It is never bulk
    // payload storage; only the selected lanes are written by the released FU.
    wire pred_response;
    wire [P-1:0] pred_result;
    wire [P-1:0] pred_lanes;
    wire pred_illegal;
    logic [PREDICATE_DEPTH-1:0] pred_owned;
    logic [CI-1:0] pred_context[PREDICATE_DEPTH];
    logic [V-1:0] pred_version[PREDICATE_DEPTH];
    wire need_pred_a = command_class == CPT_CMD_PREDICATE && opcode >= 3 && opcode <= 7;
    wire need_pred_b = command_class == CPT_CMD_PREDICATE && opcode >= 5 && opcode <= 7;
    wire pred_sources_ok = (!need_pred_a || source_a < PREDICATE_DEPTH &&
        pred_owned[source_a] && pred_context[source_a] == active_context &&
        pred_version[source_a] == active_version) && (!need_pred_b ||
        source_b < PREDICATE_DEPTH && pred_owned[source_b] &&
        pred_context[source_b] == active_context && pred_version[source_b] == active_version);
    wire pred_issue = effects && (command_class == CPT_CMD_PREDICATE ||
        command_class == CPT_CMD_COMPARE) && pred_sources_ok;
    wire [P-1:0] active_lanes = P'(mask) & P'(configured_mask);
    wire comparison;
    logic [4:0] alu_opcode;
    wire [31:0] alu_result;

    always @* begin
        case (opcode)
            0: alu_opcode = scalar_alu_pkg::ALU_EQ;
            1: alu_opcode = scalar_alu_pkg::ALU_NE;
            2: alu_opcode = scalar_alu_pkg::ALU_LT;
            3: alu_opcode = scalar_alu_pkg::ALU_LE;
            4: alu_opcode = scalar_alu_pkg::ALU_GT;
            5: alu_opcode = scalar_alu_pkg::ALU_GE;
            6: alu_opcode = scalar_alu_pkg::ALU_EQ;
            7: alu_opcode = scalar_alu_pkg::ALU_NE;
            default: alu_opcode = scalar_alu_pkg::ALU_EQ;
        endcase
    end

    wire [63:0] rf_data;
    wire rf_sources_ok;
    wire [31:0] compare_a = command_meta[56] ? rf_data[31:0] : operand_a;
    wire [31:0] compare_b = opcode == 6 || opcode == 7 ? 32'd0 :
        command_meta[57] ? rf_data[63:32] : operand_b;
    if (ENABLE_PREDICATE) begin : g_compare
        scalar_alu #(.DATA_WIDTH(32), .SUPPORT_SATURATION(0), .SUPPORT_MINMAX(0)) u_compare (
            .i_enable(effects && command_class == CPT_CMD_COMPARE && rf_sources_ok),
            .i_opcode(alu_opcode),
            .i_operand_a(compare_a),
            .i_operand_b(compare_b),
            .i_predicate(1'b1),
            .i_signed(signed_compare),
            .i_saturate(1'b0),
            .o_result(alu_result),
            .o_predicate(comparison)
        );
    end else begin : g_no_compare
        assign alu_result = '0;
        assign comparison = '0;
    end

    if (ENABLE_PREDICATE) begin : g_predicate
        predicate_unit #(.PRED_DEPTH(PREDICATE_DEPTH), .NUM_LANES(P)) u_predicate (
            .i_clk(i_clk),
            .i_rstb(storage_rstb),
            .i_clock_enable(enable),
            .i_valid(pred_issue && (command_class != CPT_CMD_COMPARE || rf_sources_ok)),
            .i_opcode(command_class == CPT_CMD_COMPARE ? 4'd2 : opcode),
            .i_lane_mask(active_lanes),
            .i_source_a_addr(PR_BITS'(source_a)),
            .i_source_b_addr(PR_BITS'(source_b)),
            .i_destination_addr(PR_BITS'(destination)),
            .i_predicate_input(command_class == CPT_CMD_COMPARE ? {P{comparison}} :
                command_meta[58] ? command_predicate : P'(operand_a)),
            .i_write_enable(write_enable),
            .o_valid(pred_response),
            .o_result(pred_result),
            .o_result_valid(pred_lanes),
            .o_illegal_operation(pred_illegal)
        );
    end else begin : g_no_predicate
        assign pred_response = '0;
        assign pred_result = '0;
        assign pred_lanes = '0;
        assign pred_illegal = '0;
    end

    // Compact registers have a published type, context and version for every
    // legal read. Data itself needs no bulk reset once validity is cleared.
    logic [CONTROL_REGISTER_DEPTH-1:0] rf_valid;
    logic [3:0] rf_type[CONTROL_REGISTER_DEPTH];
    logic [CI-1:0] rf_context[CONTROL_REGISTER_DEPTH];
    logic [V-1:0] rf_version[CONTROL_REGISTER_DEPTH];
    wire rf_a_valid = source_a < CONTROL_REGISTER_DEPTH && rf_valid[source_a] &&
        rf_context[source_a] == active_context && rf_version[source_a] == active_version &&
        rf_type[source_a] == register_type;
    wire rf_b_valid = source_b < CONTROL_REGISTER_DEPTH && rf_valid[source_b] &&
        rf_context[source_b] == active_context && rf_version[source_b] == active_version &&
        rf_type[source_b] == register_type;
    assign rf_sources_ok = (!command_meta[56] || rf_a_valid) &&
        (!command_meta[57] || rf_b_valid);
    wire rf_write = effects && command_class == CPT_CMD_STATUS && opcode == 1 &&
        destination < CONTROL_REGISTER_DEPTH && register_type >= 1 && register_type <= 6;

    register_file #(.DATA_WIDTH(32), .DEPTH(CONTROL_REGISTER_DEPTH)) u_control_registers (
        .i_clk(i_clk),
        .i_read_enable({enable && rf_b_valid, enable && rf_a_valid}),
        .i_read_address({RF_BITS'(source_b), RF_BITS'(source_a)}),
        .o_read_data(rf_data),
        .i_write_enable(rf_write),
        .i_write_address(RF_BITS'(destination)),
        .i_write_data(operand_a)
    );

    // One namespace uses the released event bank and its documented mutation
    // arbiter. A pending command waits for its own native accepted/rejected pulse.
    wire eb_configured;
    wire eb_init_ready;
    wire eb_post_ready;
    wire eb_post_accepted;
    wire eb_post_rejected;
    wire eb_ack_ready;
    wire eb_ack_accepted;
    wire eb_ack_rejected;
    wire eb_wait_ready;
    wire eb_wait_armed;
    wire eb_wait_rejected;
    wire eb_cancel_ready;
    wire eb_cancel_done;
    wire eb_cancel_missing;
    wire eb_barrier_ready;
    wire eb_barrier_configured;
    wire eb_barrier_rejected;
    wire eb_arrival_ready;
    wire eb_arrival_accepted;
    wire eb_arrival_rejected;
    wire eb_wait_valid;
    wire eb_wait_status;
    wire [NUM_EVENTS-1:0] eb_wait_mask;
    wire [NUM_EVENTS-1:0] eb_wait_consumed;
    wire [7:0] eb_wait_tag;
    wire [WI_BITS-1:0] eb_wait_slot;
    wire eb_release_valid;
    wire [BI_BITS-1:0] eb_release_id;
    wire [3:0] eb_release_generation;
    wire [7:0] eb_release_tag;
    wire [MAX_PARTICIPANTS-1:0] eb_release_mask;
    wire [NUM_EVENTS*EVENT_COUNT_WIDTH-1:0] eb_counts;
    wire [NUM_WAIT_SLOTS-1:0] eb_wait_active;
    wire [NUM_BARRIERS*4-1:0] eb_generations;
    wire [NUM_BARRIERS*MAX_PARTICIPANTS-1:0] eb_arrivals;
    wire [NUM_BARRIERS-1:0] eb_barrier_enabled;
    wire eb_idle;
    wire [4:0] egress_valid;
    wire [4:0] egress_ready;
    wire [1279:0] egress_records;
    wire egress_busy;
    wire egress_out_valid;
    wire [255:0] egress_out;
    cpt_record_t ingress;
    wire event_input_valid;
    wire [31:0] event_input_count;

    tile_shell_queue #(
        .WIDTH(256),
        .DEPTH(EVENT_INPUT_FIFO_DEPTH),
        .PROTECTION(EVENT_PROTECTION)
    ) u_event_input (
        .i_clk(i_clk),
        .i_rstb(storage_rstb),
        .i_flush(flush),
        .i_admit(enable &&!fatal_now),
        .i_deliver(enable &&!fatal_now),
        .i_valid(o_body_event_in_valid[0]),
        .o_ready(i_body_event_in_ready[0]),
        .i_data(o_body_event_in_payload),
        .o_valid(event_input_valid),
        .i_ready(ingress_ready),
        .o_data(ingress),
        .o_count(event_input_count),
        .o_bad(event_input_fatal)
    );

    logic [MAX_EVENT_SOURCES-1:0] sequence_valid;
    logic [15:0] last_sequence[MAX_EVENT_SOURCES];
    wire sequence_ok = ingress.source < MAX_EVENT_SOURCES &&
        (!sequence_valid[ingress.source] ? ingress.sequence_number == 0 :
        last_sequence[ingress.source] != 16'hffff &&
        ingress.sequence_number == last_sequence[ingress.source] + 1'b1);
    wire ingress_identity = ingress.owner == i_owner && ingress.epoch == epoch &&
        ingress.context_version == active_version && ingress.namespace_id == 0 &&
        ingress.package_version == package_version && ingress.route_version == route_version &&
        ingress.reserved == 0 && ingress.envelope[31:3] ==
            (29'(i_kernel) << CI | 29'(active_context)) &&
        (ingress.envelope[2:0] == 7 || ingress.envelope[2:0] == 1 &&
        (ingress.kind == CPT_RECORD_RESPONSE || ingress.kind == CPT_RECORD_SAFE));
    wire ingress_known = ^ingress !== 1'bx;
    wire ingress_legal = ingress_identity && ingress_known && sequence_ok &&
        (ingress.kind == CPT_RECORD_POST && ingress.event_id < NUM_EVENTS &&
        event_enable[ingress.event_id] && ingress.payload == 0 &&
        ingress.flags == 0 && ingress.opcode == 0 ||
        ingress.kind == CPT_RECORD_FORWARD || ingress.kind == CPT_RECORD_RESPONSE ||
        ingress.kind == CPT_RECORD_SAFE);
    wire external_post = event_input_valid === 1'b1 && ingress_legal &&
        ingress.kind == CPT_RECORD_POST;
    wire external_action = event_input_valid === 1'b1 && ingress_legal &&
        (ingress.kind == CPT_RECORD_RESPONSE || ingress.kind == CPT_RECORD_SAFE);
    wire command_post = effects && command_class == CPT_CMD_EVENT && opcode == 0 &&
        object_id < NUM_EVENTS;
    wire command_ack = effects && command_class == CPT_CMD_EVENT && (opcode == 1 || opcode == 2)
        && object_id < NUM_EVENTS;
    wire command_wait = effects && command_class == CPT_CMD_EVENT && (opcode == 3 || opcode == 4)
        && object_id < NUM_WAIT_SLOTS && mask != 0 && (mask >> NUM_EVENTS) == 0;
    wire command_cancel = effects && command_class == CPT_CMD_EVENT && opcode == 5 &&
        object_id < NUM_WAIT_SLOTS;
    wire command_barrier = effects && command_class == CPT_CMD_BARRIER && opcode == 0 &&
        object_id < NUM_BARRIERS && operand_a != 0 && (operand_a >> MAX_PARTICIPANTS) == 0;
    wire command_arrive = effects && command_class == CPT_CMD_BARRIER && opcode == 1 &&
        object_id < NUM_BARRIERS && participant < MAX_PARTICIPANTS;
    wire action_response_ready;
    assign ingress_ready = running &&!fatal_now && initialized
            && event_initialized &&!context_change && (external_action ?
            action_response_ready && egress_ready[3] :
        external_post ? !command_post && eb_post_ready : egress_ready[3]);
    wire ingress_fire = ingress_ready && event_input_valid === 1'b1;
    wire post_external = external_post &&!command_post;

    if (ENABLE_EVENT_BARRIER) begin : g_events
        event_barrier #(
            .NUM_EVENTS(NUM_EVENTS),
            .EVENT_COUNT_WIDTH(EVENT_COUNT_WIDTH),
            .NUM_WAIT_SLOTS(NUM_WAIT_SLOTS),
            .WAIT_RESULT_QUEUE_DEPTH(WAIT_RESULT_QUEUE_DEPTH),
            .NUM_BARRIERS(NUM_BARRIERS),
            .MAX_PARTICIPANTS(MAX_PARTICIPANTS),
            .BARRIER_RELEASE_QUEUE_DEPTH(BARRIER_RELEASE_QUEUE_DEPTH),
            .GENERATION_WIDTH(4),
            .CONTEXT_ID_WIDTH(CI),
            .WAITER_TAG_WIDTH(8),
            .BARRIER_TAG_WIDTH(8),
            .PROTECT_STATE(EVENT_PROTECTION)
        ) u_events (
            .i_clk(i_clk),
            .i_rstb(unit_rstb),
            .i_flush(flush),
            .i_error_clear(enable),
            .i_config_valid(live && initialized &&!event_init_sent),
            .i_post_valid(enable && (command_post || post_external)),
            .i_ack_valid(command_ack),
            .i_wait_valid(command_wait),
            .i_wait_cancel_valid(command_cancel),
            .i_wait_result_ready(egress_ready[2] && enable),
            .i_barrier_config_valid(command_barrier),
            .i_barrier_config_enable(1'b1),
            .i_barrier_release_event_enable(command_meta[59]),
            .i_barrier_arrival_valid(command_arrive),
            .i_barrier_release_ready(egress_ready[1] && enable),
            .i_wait_consume(command_meta[59]),
            .i_config_context_id({CI{1'b0}}),
            .i_post_context_id({CI{1'b0}}),
            .i_ack_context_id({CI{1'b0}}),
            .i_wait_context_id({CI{1'b0}}),
            .i_wait_cancel_context_id({CI{1'b0}}),
            .i_barrier_context_id({CI{1'b0}}),
            .i_barrier_arrival_context_id({CI{1'b0}}),
            .i_config_event_enable(event_enable),
            .i_wait_event_mask(NUM_EVENTS'(mask)),
            .i_post_event_id(post_external ? EI_BITS'(ingress.event_id) : EI_BITS'(object_id)),
            .i_ack_event_id(EI_BITS'(object_id)),
            .i_barrier_release_event_id(EI_BITS'(sub_id)),
            .i_ack_mode(opcode == 2 ? 2'd1 : 2'd0),
            .i_wait_mode(opcode == 4 ? 2'd1 : 2'd0),
            .i_wait_slot(WI_BITS'(object_id)),
            .i_wait_cancel_slot(WI_BITS'(object_id)),
            .i_wait_tag(tag),
            .i_wait_cancel_tag(tag),
            .i_barrier_config_id(BI_BITS'(object_id)),
            .i_barrier_arrival_id(BI_BITS'(object_id)),
            .i_barrier_expected_mask(MAX_PARTICIPANTS'(operand_a)),
            .i_barrier_tag(tag),
            .i_barrier_participant_id(PA_BITS'(participant)),
            .i_barrier_arrival_generation(generation),
            .o_config_ready(eb_init_ready),
            .o_config_accepted(eb_configured),
            .o_post_ready(eb_post_ready),
            .o_post_accepted(eb_post_accepted),
            .o_post_rejected(eb_post_rejected),
            .o_ack_ready(eb_ack_ready),
            .o_ack_accepted(eb_ack_accepted),
            .o_ack_rejected(eb_ack_rejected),
            .o_wait_ready(eb_wait_ready),
            .o_wait_armed(eb_wait_armed),
            .o_wait_rejected(eb_wait_rejected),
            .o_wait_cancel_ready(eb_cancel_ready),
            .o_wait_canceled(eb_cancel_done),
            .o_wait_cancel_not_found(eb_cancel_missing),
            .o_wait_result_valid(eb_wait_valid),
            .o_wait_result_status(eb_wait_status),
            .o_barrier_config_ready(eb_barrier_ready),
            .o_barrier_configured(eb_barrier_configured),
            .o_barrier_config_rejected(eb_barrier_rejected),
            .o_barrier_arrival_ready(eb_arrival_ready),
            .o_barrier_arrival_accepted(eb_arrival_accepted),
            .o_barrier_arrival_rejected(eb_arrival_rejected),
            .o_barrier_release_valid(eb_release_valid),
            .o_idle(eb_idle),
            .o_fatal_error(eb_fatal),
            .o_wait_result_matched_mask(eb_wait_mask),
            .o_wait_result_consumed_mask(eb_wait_consumed),
            .o_event_count(eb_counts),
            .o_wait_slot_active(eb_wait_active),
            .o_barrier_enable(eb_barrier_enabled),
            .o_barrier_arrived(eb_arrivals),
            .o_barrier_generation(eb_generations),
            .o_wait_result_slot(eb_wait_slot),
            .o_wait_result_tag(eb_wait_tag),
            .o_barrier_release_id(eb_release_id),
            .o_barrier_release_generation(eb_release_generation),
            .o_barrier_release_tag(eb_release_tag),
            .o_barrier_release_participants(eb_release_mask)
        );
    end else begin : g_no_events
        assign eb_init_ready = '0;
        assign eb_configured = '0;
        assign eb_post_ready = '0;
        assign eb_post_accepted = '0;
        assign eb_post_rejected = '0;
        assign eb_ack_ready = '0;
        assign eb_ack_accepted = '0;
        assign eb_ack_rejected = '0;
        assign eb_wait_ready = '0;
        assign eb_wait_armed = '0;
        assign eb_wait_rejected = '0;
        assign eb_cancel_ready = '0;
        assign eb_cancel_done = '0;
        assign eb_cancel_missing = '0;
        assign eb_wait_valid = '0;
        assign eb_wait_status = '0;
        assign eb_barrier_ready = '0;
        assign eb_barrier_configured = '0;
        assign eb_barrier_rejected = '0;
        assign eb_arrival_ready = '0;
        assign eb_arrival_accepted = '0;
        assign eb_arrival_rejected = '0;
        assign eb_release_valid = '0;
        assign eb_idle = 1'b1;
        assign eb_fatal = '0;
        assign eb_wait_mask = '0;
        assign eb_wait_consumed = '0;
        assign eb_counts = '0;
        assign eb_wait_active = '0;
        assign eb_barrier_enabled = '0;
        assign eb_arrivals = '0;
        assign eb_generations = '0;
        assign eb_wait_slot = '0;
        assign eb_wait_tag = '0;
        assign eb_release_id = '0;
        assign eb_release_generation = '0;
        assign eb_release_tag = '0;
        assign eb_release_mask = '0;
    end

    wire [LD*2-1:0] loop_modes;
    wire [LD*IW-1:0] loop_initial;
    wire [LD*IW-1:0] loop_bound;
    wire [LD*IW-1:0] loop_step;
    wire [LD*TW-1:0] loop_trips;
    wire [LD*3-1:0] loop_compares;

    for (genvar level = 0; level < LD; level++) begin : g_loop_image
        assign loop_initial[level*IW+:IW] = image[512+level*LOOP_BITS+:IW];
        assign loop_bound[level*IW+:IW] = image[512+level*LOOP_BITS+IW+:IW];
        assign loop_step[level*IW+:IW] = image[512+level*LOOP_BITS+2*IW+:IW];
        assign loop_trips[level*TW+:TW] = image[512+level*LOOP_BITS+3*IW+:TW];
        assign loop_modes[level*2+:2] = image[512+level*LOOP_BITS+3*IW+TW+:2];
        assign loop_compares[level*3+:3] = image[512+level*LOOP_BITS+3*IW+TW+2+:3];
    end

    wire loop_config_accepted;
    wire loop_config_rejected;
    wire loop_config_ready;
    wire loop_start_ready;
    wire loop_start_accepted;
    wire loop_start_rejected;
    wire loop_control_ready;
    wire loop_control_accepted;
    wire loop_control_rejected;
    wire loop_token_valid;
    wire loop_token_ready;
    wire [LD*IW-1:0] loop_indices;
    wire [LD*TW-1:0] loop_ordinals;
    wire [LD-1:0] loop_first;
    wire [LD-1:0] loop_last;
    wire [63:0] loop_linear;
    wire [7:0] loop_run;
    wire [7:0] current_loop_run;
    wire [7:0] completed_loop_run;
    wire [15:0] loop_epoch;
    wire loop_complete;
    wire [1:0] loop_completion_status;
    wire [63:0] loop_iterations;
    wire loop_active;
    wire loop_suspended;
    wire loop_idle;
    wire explicit_loop_control = effects && command_class == CPT_CMD_LOOP_CONTROL &&
        opcode >= 1 && opcode <= 3;
    wire implicit_pause = o_body_suspend_request && loop_active &&!loop_suspended;
    wire implicit_resume = o_body_resume && loop_suspended;
    wire loop_control_valid = explicit_loop_control || implicit_pause || implicit_resume;
    wire [1:0] loop_control_command = opcode == 1 ? 2'd0 : opcode == 2 ? 2'd1 : 2'd2;

    if (ENABLE_LOOP_CONTROLLER) begin : g_loop
        loop_controller #(
            .MAX_LOOP_DEPTH(LD),
            .INDEX_WIDTH(IW),
            .TRIP_COUNT_WIDTH(TW),
            .LINEAR_COUNT_WIDTH(64),
            .II_WIDTH(8),
            .CONTEXT_ID_WIDTH(CI),
            .RUN_ID_WIDTH(8),
            .CONFIG_EPOCH_WIDTH(16),
            .NUM_EVENTS(NUM_EVENTS),
            .PROTECT_STATE(CONTROL_PROTECTION != 0)
        ) u_loop (
            .i_clk(i_clk),
            .i_rstb(unit_rstb),
            .i_flush(flush),
            .i_error_clear(enable),
            .i_config_valid(live && initialized &&!loop_init_sent),
            .o_config_ready(loop_config_ready),
            .i_config_depth(DEPTH_BITS'(loop_depth)),
            .i_config_level_mode(loop_modes),
            .i_config_initial(loop_initial),
            .i_config_bound(loop_bound),
            .i_config_step(loop_step),
            .i_config_trip_count(loop_trips),
            .i_config_compare(loop_compares),
            .i_config_initiation_interval(loop_ii),
            .i_config_context_id(active_context),
            .i_config_completion_event_enable(1'b1),
            .i_config_completion_event_id(loop_event),
            .o_config_accepted(loop_config_accepted),
            .o_config_rejected(loop_config_rejected),
            .i_start_valid(effects && command_class == CPT_CMD_LOOP_CONTROL && opcode == 0),
            .o_start_ready(loop_start_ready),
            .i_start_context_id(active_context),
            .i_start_run_id(tag),
            .o_start_accepted(loop_start_accepted),
            .o_start_rejected(loop_start_rejected),
            .i_control_valid(loop_control_valid),
            .o_control_ready(loop_control_ready),
            .i_control_command(explicit_loop_control ? loop_control_command :
                implicit_resume ? 2'd1 : 2'd0),
            .i_control_context_id(active_context),
            .i_control_run_id(explicit_loop_control ? tag : current_loop_run),
            .o_control_accepted(loop_control_accepted),
            .o_control_rejected(loop_control_rejected),
            .i_execution_quiescent(!loop_frame_active),
            .o_iteration_valid(loop_token_valid),
            .i_iteration_ready(loop_token_ready),
            .o_iteration_index(loop_indices),
            .o_iteration_ordinal(loop_ordinals),
            .o_iteration_first_mask(loop_first),
            .o_iteration_last_mask(loop_last),
            .o_iteration_linear(loop_linear),
            .o_iteration_run_id(loop_run),
            .o_iteration_epoch(loop_epoch),
            .o_completion_valid(loop_complete),
            .i_completion_ready(!eb_wait_valid && egress_ready[2] && enable),
            .o_completion_run_id(completed_loop_run),
            .o_completion_status(loop_completion_status),
            .o_completion_iterations(loop_iterations),
            .o_current_run_id(current_loop_run),
            .o_active(loop_active),
            .o_suspended(loop_suspended),
            .o_idle(loop_idle),
            .o_fatal_error(loop_fatal)
        );
    end else begin : g_no_loop
        assign loop_config_ready = '0;
        assign loop_config_accepted = '0;
        assign loop_config_rejected = '0;
        assign loop_start_ready = '0;
        assign loop_start_accepted = '0;
        assign loop_start_rejected = '0;
        assign loop_control_ready = '0;
        assign loop_control_accepted = '0;
        assign loop_control_rejected = '0;
        assign loop_token_valid = '0;
        assign loop_indices = '0;
        assign loop_ordinals = '0;
        assign loop_first = '0;
        assign loop_last = '0;
        assign loop_linear = '0;
        assign loop_run = '0;
        assign loop_epoch = '0;
        assign loop_complete = '0;
        assign completed_loop_run = '0;
        assign loop_completion_status = '0;
        assign loop_iterations = '0;
        assign current_loop_run = '0;
        assign loop_active = '0;
        assign loop_suspended = '0;
        assign loop_idle = 1'b1;
        assign loop_fatal = '0;
    end

    function automatic cpt_record_t new_record(input logic [3:0] kind);
        cpt_record_t record;
        record = '0;
        record.envelope = 32'(i_kernel) << (CI + 3) | 32'(active_context) << 3 | 32'd7;
        record.kind = kind;
        record.owner = i_owner;
        record.context_version = active_version;
        record.epoch = epoch;
        record.source = 8'(TILE_ID);
        record.participants = targets;
        record.package_version = package_version;
        record.route_version = route_version;
        return record;
    endfunction

    cpt_record_t action_request;
    cpt_record_t action_output;
    cpt_record_t terminal_output;
    cpt_record_t wait_record;
    cpt_record_t release_record;
    cpt_record_t loop_record;
    cpt_record_t forwarded_record;
    wire action_ready;
    wire action_issue_error;
    wire action_output_valid;
    wire terminal_valid;
    wire action_response_error;
    wire actions_busy;
    wire action_uncertain;
    wire timeout_event;
    wire legal_action = ENABLE_ACTIONS && opcode <= CPT_ACTION_RECOVER &&
        opcode != CPT_ACTION_CHECKPOINT && targets != 0 &&
        (targets >> MAX_PARTICIPANTS) == 0 &&
        (opcode != CPT_ACTION_ACTIVATE_CONTEXT || SUPPORT_CONTEXT_COORDINATION &&
            package_version != 0 && route_version != 0) &&
        (opcode == CPT_ACTION_ACTIVATE_CONTEXT || SUPPORT_CLUSTER_LIFECYCLE);

    always @* begin
        action_request = new_record(CPT_RECORD_REQUEST);
        action_request.opcode = opcode;
        action_request.tag = tag;
        action_request.participants = targets;
        action_request.payload = command_data;
        wait_record = new_record(CPT_RECORD_WAIT);
        wait_record.event_id = 8'(eb_wait_slot);
        wait_record.tag = eb_wait_tag;
        wait_record.flags = {3'b0, eb_wait_status};
        wait_record.payload = 64'(eb_wait_mask) | 64'(eb_wait_consumed) << 32;
        release_record = new_record(CPT_RECORD_BARRIER);
        release_record.event_id = 8'(eb_release_id);
        release_record.tag = eb_release_tag;
        release_record.participants = 16'(eb_release_mask);
        release_record.payload = 64'(eb_release_generation);
        loop_record = new_record(CPT_RECORD_LOOP);
        loop_record.event_id = 8'(loop_event);
        loop_record.tag = completed_loop_run;
        loop_record.flags = {2'b0, loop_completion_status};
        loop_record.payload = loop_iterations;
        forwarded_record = ingress;

        if (!ingress_legal || external_action && action_response_error) begin
            forwarded_record = new_record(CPT_RECORD_REJECT);
            forwarded_record.flags = 4'd1;
            forwarded_record.tag = ingress.tag;
        end
    end

    if (ENABLE_ACTIONS) begin : g_actions
        cpt_actions #(
            .SLOTS(MAX_OUTSTANDING_ACTIONS), .SUPPORT_TIMEOUT(SUPPORT_TIMEOUT)
        ) u_actions (
            .i_clk(i_clk),
            .i_rstb(storage_rstb),
            .i_flush(flush),
            .i_enable(enable && started &&!fatal_now && i_execution_state != TILE_SUSPENDED),
            .i_issue(effects && command_class == CPT_CMD_ACTION && legal_action),
            .i_request(action_request),
            .i_timeout(timeout),
            .o_issue_ready(action_ready),
            .o_issue_error(action_issue_error),
            .i_response_valid(external_action && ingress_ready),
            .i_response(ingress),
            .o_response_ready(action_response_ready),
            .o_response_error(action_response_error),
            .o_request_valid(action_output_valid),
            .o_request(action_output),
            .i_request_ready(egress_ready[0] &&!terminal_valid),
            .o_terminal_valid(terminal_valid),
            .o_terminal(terminal_output),
            .i_terminal_ready(egress_ready[0]),
            .o_busy(actions_busy),
            .o_uncertain(action_uncertain),
            .o_timeout_event(timeout_event)
        );
    end else begin : g_no_actions
        assign action_ready = 1'b0;
        assign action_issue_error = 1'b1;
        assign action_response_ready = 1'b1;
        assign action_response_error = external_action;
        assign action_output_valid = 1'b0;
        assign action_output = '0;
        assign terminal_valid = 1'b0;
        assign terminal_output = '0;
        assign actions_busy = 1'b0;
        assign action_uncertain = 1'b0;
        assign timeout_event = 1'b0;
    end

    assign egress_valid = {pending_event && phase == CPT_RETIRE,
        event_input_valid === 1'b1 && ingress_ready &&
            (!ingress_legal || ingress.kind == CPT_RECORD_FORWARD ||
            external_action && action_response_error),
        eb_wait_valid || loop_complete, eb_release_valid,
        terminal_valid || action_output_valid};
    assign egress_records = {command_record, forwarded_record,
        eb_wait_valid ? wait_record : loop_record, release_record,
        terminal_valid ? terminal_output : action_output};

    cpt_egress #(
        .DEPTH(EVENT_OUTPUT_FIFO_DEPTH),
        .MAX_BURST(MAX_PRIORITY_BURST),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_egress (
        .i_clk(i_clk),
        .i_rstb(storage_rstb),
        .i_flush(flush),
        .i_enable(enable &&!fatal_now),
        .i_valid(egress_valid),
        .o_ready(egress_ready),
        .i_records(egress_records),
        .o_valid(egress_out_valid),
        .i_ready(o_body_event_out_ready[0]),
        .o_record(egress_out),
        .o_busy(egress_busy),
        .o_fatal(egress_fatal)
    );

    assign i_body_event_out_valid = egress_out_valid && enable &&!fatal_now;
    assign i_body_event_out_payload = egress_out;

    // A framed iteration consists of its linear header followed by selected
    // index/ordinal pairs. The native loop holds its state until FINAL DELIVERY
    // through the public shell output, not merely until admission to a queue.
    logic loop_await_delivery;
    logic [3:0] loop_beat;
    logic [3:0] loop_beats;
    logic [3:0] selected_level;
    logic [3:0] exported_count;
    wire loop_frame_valid = loop_token_valid &&!loop_await_delivery &&
        (!o_body_suspend_request || loop_frame_active) &&
        (loop_frame_active || phase != CPT_RETIRE) && enable &&!fatal_now;
    wire [63:0] packed_index;
    wire [63:0] packed_ordinal;

    packer #(
        .NUM_ELEMENTS(1),
        .SRC_ELEMENT_WIDTH(IW),
        .DST_ELEMENT_WIDTH(64),
        .SUPPORT_SATURATION(0),
        .SUPPORT_REVERSE(0)
    ) u_index_format (
        .i_clk(i_clk),
        .i_rstb(storage_rstb),
        .i_flush(flush),
        .i_valid(loop_token_valid),
        .i_data(loop_indices[selected_level*IW+:IW]),
        .i_lane_valid(1'b1),
        .i_signed(1'b1),
        .i_saturate(1'b0),
        .i_reverse(1'b0),
        .i_last(1'b1),
        .i_user(1'b0),
        .i_ready(1'b1),
        .o_data(packed_index)
    );

    packer #(
        .NUM_ELEMENTS(1),
        .SRC_ELEMENT_WIDTH(TW),
        .DST_ELEMENT_WIDTH(64),
        .SUPPORT_SATURATION(0),
        .SUPPORT_REVERSE(0)
    ) u_ordinal_format (
        .i_clk(i_clk),
        .i_rstb(storage_rstb),
        .i_flush(flush),
        .i_valid(loop_token_valid),
        .i_data(loop_ordinals[selected_level*TW+:TW]),
        .i_lane_valid(1'b1),
        .i_signed(1'b0),
        .i_saturate(1'b0),
        .i_reverse(1'b0),
        .i_last(1'b1),
        .i_user(1'b0),
        .i_ready(1'b1),
        .o_data(packed_ordinal)
    );

    logic [63:0] loop_payload;
    logic [127:0] loop_metadata;

    always @* begin
        exported_count = '0;
        selected_level = '0;

        for (int level = 0; level < LD; level++) begin
            if (loop_export[level]) begin
                if (exported_count == ((loop_beat - 1) >> 1)) selected_level = 4'(level);
                exported_count = exported_count + 1'b1;
            end
        end

        loop_beats = 1 + (exported_count << 1);
        loop_payload = loop_linear;

        if (loop_beat != 0) begin
            if (loop_beat[0])
                loop_payload = packed_index;
            else loop_payload = packed_ordinal;
        end

        loop_metadata = '0;
        loop_metadata[CI-1:0] = active_context;
        loop_metadata[CI+:V] = active_version;
        loop_metadata[32+:LD] = loop_first;
        loop_metadata[40+:LD] = loop_last;
        loop_metadata[48+:8] = loop_run;
        loop_metadata[56+:16] = loop_epoch;
        loop_metadata[72+:4] = loop_beat;
        loop_metadata[76+:4] = loop_beats;
        loop_metadata[122] = loop_beat == 0;
        loop_metadata[123] = loop_beat == loop_beats - 1'b1;
        loop_metadata[127:124] = 4'hc;
    end

    wire command_data_valid = phase == CPT_RETIRE
            && pending_data &&!loop_frame_active &&!loop_await_delivery && enable &&!fatal_now;
    wire loop_send = loop_frame_valid &&!command_data_valid;
    wire loop_body_fire = loop_send && o_body_data_out_ready[0] === 1'b1;
    assign loop_token_ready = loop_await_delivery && i_loop_delivered && enable;
    assign i_body_data_out_valid = NO'(command_data_valid || loop_send);
    logic [127:0] result_metadata;

    always @* begin
        result_metadata = command_meta;
        result_metadata[121] = result_error;
        result_metadata[122] = suppressed;
        result_metadata[127:124] = 4'hb;
    end

    assign i_body_data_out_payload = command_data_valid ? result : loop_payload;
    assign i_body_data_out_metadata = command_data_valid ? result_metadata : loop_metadata;

    for (genvar port = 0; port < PO; port++) begin : g_predicate_output
        logic [PM-1:0] meta;

        always @* begin
            meta = '0;
            meta[CI-1:0] = active_context;
            meta[CI+:V] = active_version;
            meta[32+:P] = result_valid_lanes;
            meta[48+:8] = tag;
        end

        assign i_body_predicate_out_valid[port] = enable &&!fatal_now &&
            phase == CPT_RETIRE && pending_predicate[port];
        assign i_body_predicate_out_payload[port*P+:P] = result_predicate;
        assign i_body_predicate_out_metadata[port*PM+:PM] = meta;
    end

    wire event_engine_quiet = eb_wait_active == 0
            && eb_arrivals == 0 &&!eb_wait_valid &&!eb_release_valid && event_input_count == 0;
    wire all_native_quiet = !loop_active &&!loop_complete &&!loop_frame_active &&
        !loop_await_delivery &&!actions_busy &&!egress_busy && event_engine_quiet;
    wire quiet = phase == CPT_IDLE && all_native_quiet;
    wire suspension_safe = phase == CPT_IDLE &&!loop_frame_active &&
        !loop_await_delivery &&!loop_complete &&!egress_busy &&!action_uncertain &&
        (!loop_active || loop_suspended);
    assign i_body_busy = live &&!suspension_safe;
    assign i_body_idle = !i_body_busy;
    assign i_body_safe_point = known_reset
            && phase == CPT_IDLE &&!loop_frame_active &&!loop_await_delivery &&
            !loop_complete &&!egress_busy &&!action_uncertain &&
        (!loop_active || loop_suspended);
    assign i_body_drain_done = enable && quiet && o_body_data_in_valid == 0 &&
        o_body_predicate_in_valid == 0 && o_body_event_in_valid == 0;
    assign i_body_completed = live && completed && quiet &&!context_change &&
        (!sequence_enable || terminal_context);
    // Bit zero is an external-input wait; bit one wakes on data readiness.
    // Native pipelines, egress and timeout monitors require enabled body cycles.
    assign i_body_stall_reasons = {6'd0,
        pending_data && o_body_data_out_ready[0] !== 1'b1,
        phase == CPT_IDLE &&!completed &&!loop_active &&!loop_complete &&
        !actions_busy &&!egress_busy &&
        initialized && event_initialized && loop_initialized && eb_idle &&
        o_body_data_in_valid == 0};
    assign i_body_error = fatal_now;
    assign i_body_fatal_error = fatal_now;
    assign i_body_error_code = fatal_now ? 8'h8f : 8'd0;
    assign i_body_wakeup_required = o_body_event_in_valid != 0 || event_input_count != 0;
    assign o_advance_valid = live && sequence_enable && completed
            && quiet &&!context_change &&!terminal_context && eb_counts == 0;
    assign o_advance_context = next_context;

    logic native_ready;
    logic native_done;
    logic native_error;

    always @* begin
        native_ready = 1'b1;
        native_done = 1'b1;
        native_error = 1'b0;
        command_legal = command_association_legal && allowed_classes[command_class]
            && command_class <= 7 &&
            (command_meta[63:62] == 0) && command_meta[123:121] == 0 &&
            (!REQUIRE_CANONICAL_FORMAT || (command_meta[31:0] >> (CI + V)) == 0 &&
            command_meta[127:124] == 0);

        case (command_class)
            CPT_CMD_PREDICATE, CPT_CMD_COMPARE: begin
                command_legal = command_legal && (mask >> P) == 0 && pred_sources_ok &&
                    destination < PREDICATE_DEPTH && (!command_meta[58] ||
                    command_meta[54]) && (command_class == CPT_CMD_COMPARE ?
                    opcode <= 7 && rf_sources_ok
            && (required_type == 0 ||!command_meta[56] &&!command_meta[57] ||
                required_type == register_type) :
                    opcode <= 8);
                native_done = pred_response;
                native_error = pred_illegal;
            end
            CPT_CMD_LOOP_CONFIG: begin
                command_legal = command_legal && opcode == 0 &&!loop_active;
            end
            CPT_CMD_LOOP_CONTROL: begin
                command_legal = command_legal && opcode <= 3;
                native_ready = opcode == 0 ? loop_start_ready : loop_control_ready;
                native_done = loop_start_accepted || loop_start_rejected ||
                    loop_control_accepted || loop_control_rejected;
                native_error = loop_start_rejected || loop_control_rejected;
            end
            CPT_CMD_EVENT: begin
                command_legal = command_legal && opcode <= 6;

                case (opcode)
                    0: begin
                        command_legal = command_legal && object_id < NUM_EVENTS;
                        native_ready = eb_post_ready;
                        native_done = eb_post_accepted || eb_post_rejected;
                        native_error = eb_post_rejected;
                    end
                    1, 2: begin
                        command_legal = command_legal && object_id < NUM_EVENTS;
                        native_ready = eb_ack_ready;
                        native_done = eb_ack_accepted || eb_ack_rejected;
                        native_error = eb_ack_rejected;
                    end
                    3, 4: begin
                        command_legal = command_legal && object_id < NUM_WAIT_SLOTS && mask != 0 &&
                            (mask >> NUM_EVENTS) == 0;
                        native_ready = eb_wait_ready;
                        native_done = eb_wait_armed || eb_wait_rejected;
                        native_error = eb_wait_rejected;
                    end
                    5: begin
                        command_legal = command_legal && object_id < NUM_WAIT_SLOTS;
                        native_ready = eb_cancel_ready;
                        native_done = eb_cancel_done || eb_cancel_missing;
                        native_error = eb_cancel_missing;
                    end
                    default: begin end
                endcase
        case (command_class)
            CPT_CMD_PREDICATE, CPT_CMD_COMPARE: command_legal &= ENABLE_PREDICATE;
            CPT_CMD_LOOP_CONFIG, CPT_CMD_LOOP_CONTROL: command_legal &= ENABLE_LOOP_CONTROLLER;
            CPT_CMD_EVENT, CPT_CMD_BARRIER: command_legal &= ENABLE_EVENT_BARRIER;
            CPT_CMD_ACTION: command_legal &= ENABLE_ACTIONS;
            default: begin end
        endcase
            end
            CPT_CMD_BARRIER: begin
                command_legal = command_legal && opcode <= 2 && object_id < NUM_BARRIERS;

                if (opcode == 0) begin
                    command_legal = command_legal && operand_a != 0 &&
                        (operand_a >> MAX_PARTICIPANTS) == 0 && sub_id < NUM_EVENTS;
                    native_ready = eb_barrier_ready;
                    native_done = eb_barrier_configured || eb_barrier_rejected;
                    native_error = eb_barrier_rejected;
                end else if (opcode == 1) begin
                    command_legal = command_legal && participant < MAX_PARTICIPANTS;
                    native_ready = eb_arrival_ready;
                    native_done = eb_arrival_accepted || eb_arrival_rejected;
                    native_error = eb_arrival_rejected;
                end
            end
            CPT_CMD_ACTION: begin
                command_legal = command_legal && legal_action &&!action_issue_error;
                native_ready = action_ready;
            end
            CPT_CMD_STATUS: begin
                command_legal = command_legal && opcode <= 5 &&
                    (required_type == 0 || required_type == register_type);

                if (opcode == 0) command_legal = command_legal && rf_a_valid;

                if (opcode == 1) command_legal = command_legal
            && destination < CONTROL_REGISTER_DEPTH &&
                    register_type >= 1 && register_type <= 6;

                if (opcode == 2) command_legal = command_legal &&
                    destination < CONTROL_REGISTER_DEPTH;

                if (opcode == 3) command_legal = command_legal && object_id < NUM_EVENTS;

                if (opcode == 4) command_legal = command_legal && object_id < NUM_BARRIERS;

                if (opcode == 5) command_legal = command_legal && object_id < 16;
            end
            default: command_legal = 1'b0;
        endcase
    end

    always_ff @(posedge i_clk) begin
        if (i_rstb === 1'b0 || flush) begin
            phase <= CPT_IDLE;
            initialized <= 1'b0;
            event_initialized <= 1'b0;
                event_init_sent <= 1'b0;
                loop_init_sent <= 1'b0;
            loop_initialized <= 1'b0;
            active_context <= '0;
            active_version <= '0;
            started <= 1'b0;
            completed <= 1'b0;
            fatal <= 1'b0;
            committed_count <= '0;
            pending_data <= 1'b0;
            pending_event <= 1'b0;
            pending_predicate <= '0;
            command_data <= '0;
            command_meta <= '0;
            command_class <= '0;
            command_condition <= 1'b0;
            command_association_legal <= 1'b0;
            command_predicate <= '0;
            result <= '0;
            result_error <= 1'b0;
            result_predicate <= '0;
            result_valid_lanes <= '0;
            suppressed <= 1'b0;
            command_record <= '0;
            sequence_valid <= '0;
            pred_owned <= '0;
            rf_valid <= '0;
            loop_frame_active <= 1'b0;
            loop_await_delivery <= 1'b0;
            loop_beat <= '0;
        end else if (enable) begin
            if (eb_fatal || loop_fatal || egress_fatal || event_input_fatal) fatal <= 1'b1;

            if (context_change) begin
                initialized <= 1'b1;
                active_context <= o_body_context_id;
                active_version <= o_body_context_version;
                event_initialized <= 1'b0;
                event_init_sent <= 1'b0;
                loop_init_sent <= 1'b0;
                loop_initialized <= 1'b0;
                sequence_valid <= '0;
                pred_owned <= '0;
                rf_valid <= '0;
                completed <= 1'b0;
                committed_count <= '0;
                phase <= CPT_IDLE;
            end

            if (live && initialized &&!event_init_sent && eb_init_ready)
                event_init_sent <= 1'b1;

            if (live && initialized &&!loop_init_sent && loop_config_ready)
                loop_init_sent <= 1'b1;

            if (!ENABLE_EVENT_BARRIER || eb_configured) event_initialized <= 1'b1;

            if (!ENABLE_LOOP_CONTROLLER || loop_config_accepted) loop_initialized <= 1'b1;

            if (loop_config_rejected) fatal <= 1'b1;

            if (o_body_start) begin
                started <= 1'b1;
                completed <= 1'b0;
                committed_count <= '0;
            end

            if (ingress_fire && ingress_legal) begin
                sequence_valid[ingress.source] <= 1'b1;
                last_sequence[ingress.source] <= ingress.sequence_number;

            end
            if (loop_body_fire) begin
                loop_frame_active <= 1'b1;

                if (loop_beat == loop_beats - 1'b1) loop_await_delivery <= 1'b1;
                else loop_beat <= loop_beat + 1'b1;
            end

            if (loop_token_ready) begin
                loop_frame_active <= 1'b0;
                loop_await_delivery <= 1'b0;
                loop_beat <= '0;
            end

            if (issue) begin
                command_data <= o_body_data_in_metadata[60] ?
                    {o_body_data_in_payload[64+:32], o_body_data_in_payload[0+:32]} :
                    o_body_data_in_payload[63:0];
                command_association_legal <= (!joined_required[1] ||
                    o_body_data_in_metadata[128+:CI+V] ==
                    o_body_data_in_metadata[0+:CI+V]) &&
                    (!need_external_predicate || select_predicate < PI &&
                    o_body_predicate_in_metadata[select_predicate*PM+:CI+V] ==
                    o_body_data_in_metadata[0+:CI+V]);
                command_meta <= o_body_data_in_metadata[127:0];
                command_class <= configured_class == CPT_CMD_DISPATCH ?
                    o_body_data_in_metadata[32+:4] : configured_class;
                command_predicate <= o_body_predicate_in_payload[select_predicate*P+:P];
                command_condition <= !need_external_predicate ||
                    (select_predicate >= PI ||
                    |(o_body_predicate_in_payload[select_predicate*P+:P] &
                    P'(configured_mask) & P'(o_body_data_in_metadata[64+:16])));
                phase <= CPT_EXECUTE;
                suppressed <= 1'b0;
                result_error <= 1'b0;
                result <= '0;
                result_predicate <= '0;
                result_valid_lanes <= '0;
            end

            if (execute) begin
                if (!command_condition) begin
                    suppressed <= 1'b1;
                    phase <= CPT_RETIRE;
                    pending_data <= false_token && SUPPORT_PREDICATED_TOKEN;

                    if (false_token && SUPPORT_PREDICATED_TOKEN) begin
                        if (command_class == CPT_CMD_PREDICATE ||
                            command_class == CPT_CMD_COMPARE) begin
                            pending_predicate <= predicate_route;
                            result_predicate <= '0;
                            result_valid_lanes <= active_lanes;
                        end else begin
                            command_record <= new_record(CPT_RECORD_FORWARD);
                            command_record.flags <= 4'd4;
                            command_record.tag <= tag;
                            pending_event <= 1'b1;
                        end
                    end
                end else if (!command_legal) begin
                    result_error <= 1'b1;
                    pending_data <= 1'b1;
                    phase <= CPT_RETIRE;
                end else if (native_ready) begin
                    phase <= CPT_NATIVE_WAIT;

                    if (command_class == CPT_CMD_PREDICATE
            || command_class == CPT_CMD_COMPARE) begin
                        if (write_enable) begin
                            pred_owned[destination] <= 1'b1;
                            pred_context[destination] <= active_context;
                            pred_version[destination] <= active_version;
                        end
                    end

                    if (rf_write) begin
                        rf_valid[destination] <= 1'b1;
                        rf_type[destination] <= register_type;
                        rf_context[destination] <= active_context;
                        rf_version[destination] <= active_version;
                    end

                    if (command_class == CPT_CMD_STATUS && opcode == 2)
                        rf_valid[destination] <= 1'b0;
                end
            end

            if (phase == CPT_NATIVE_WAIT && native_done) begin
                result_error <= native_error;
                pending_data <= 1'b1;
                phase <= CPT_RETIRE;

                case (command_class)
                    CPT_CMD_PREDICATE, CPT_CMD_COMPARE: begin
                        result <= 64'(pred_result);
                        result_predicate <= pred_result;
                        result_valid_lanes <= pred_lanes;
                        if (!native_error) pending_predicate <= predicate_route;
                    end
                    CPT_CMD_EVENT: begin
                        if (opcode == 6) begin
                            command_record <= new_record(CPT_RECORD_FORWARD);
                            command_record.payload <= command_data;
                            command_record.tag <= tag;
                            command_record.event_id <= object_id;
                            pending_event <= 1'b1;
                        end
                    end
                    CPT_CMD_BARRIER: begin
                        result <= 64'(eb_generations[object_id*4+:4]);
                    end
                    CPT_CMD_ACTION: result <= 64'(tag);
                    CPT_CMD_STATUS: begin
                        case (opcode)
                            0: result <= 64'(rf_data[31:0]);
                            3: result <= 64'(eb_counts[object_id*EVENT_COUNT_WIDTH+:
                                EVENT_COUNT_WIDTH]);
                            4: result <= 64'(eb_generations[object_id*4+:4]) |
                                64'(eb_arrivals[object_id*MAX_PARTICIPANTS+:
                                    MAX_PARTICIPANTS]) << 8;
                            5: result <= 64'(o_counter_data);
                            default: result <= '0;
                        endcase
                    end
                    default: result <= '0;
                endcase
            end

            if (phase == CPT_RETIRE) begin
                if (command_data_valid && o_body_data_out_ready[0] === 1'b1)
                    pending_data <= 1'b0;

                pending_predicate <= pending_predicate & ~o_body_predicate_out_ready;

                if (pending_event && egress_ready[4]) pending_event <= 1'b0;

                if (retire) begin
                    phase <= CPT_IDLE;
                    committed_count <= committed_count + 1'b1;

                    if (command_terminal || command_limit != 0 &&
                        committed_count + 1'b1 >= command_limit) completed <= 1'b1;
                end
            end
        end
    end

    // Counter 0 observes idle monitor cycles even when the body clock is gated.
    // Counters 1..9 cover issue, retire, decode errors, waits, barriers,
    // delivered iterations, ingress, rejected ingress and action timeouts.
    // Counter 10 counts enabled command-engine cycles; 11..15 are disabled.
    wire [15:0] counter_events = {5'd0, running && phase != CPT_IDLE,
        timeout_event, ingress_fire &&!ingress_legal,
        ingress_fire, loop_token_ready, eb_release_valid && egress_ready[1],
        eb_wait_valid && egress_ready[2], execute &&!command_legal, retire, issue,
        known_reset && o_body_context_active && phase == CPT_IDLE &&
        i_execution_state >= TILE_ACTIVE && i_execution_state <= TILE_SYNC_STALL};
    wire [63:0] counter_selection;
    for (genvar n = 0; n < 16; n++) begin : g_counter_selection
        assign counter_selection[n*4+:4] = 4'(n);
    end
    assign o_counter_available = !(phase == CPT_NATIVE_WAIT &&
        command_class == CPT_CMD_STATUS && opcode == 5);

    performance_counters #(
        .COUNTER_WIDTH(32),
        .NUM_COUNTERS(16),
        .NUM_EVENTS(16),
        .INCREMENT_WIDTH(1),
        .HAS_THRESHOLD(0),
        .HAS_SNAPSHOT(0)
    ) u_counters (
        .i_clk(i_clk),
        .i_rstb(reset_b),
        .i_global_enable(i_monitor_enable && known_reset),
        .i_freeze(i_execution_state == TILE_UNALLOCATED),
        .i_counter_enable(16'h07ff),
        .i_clear({16{o_body_start}}),
        .i_event_select(counter_selection),
        .i_event_valid(counter_events),
        .i_event_increment(16'hffff),
        .i_threshold_enable(16'd0),
        .i_threshold_value(512'd0),
        .i_snapshot(1'b0),
        .i_read_enable(1'b1),
        .i_read_snapshot(1'b0),
        .i_read_index(!o_counter_available ? object_id[3:0] : i_counter_index[3:0]),
        .o_read_data(o_counter_data)
    );
endmodule
`default_nettype wire
