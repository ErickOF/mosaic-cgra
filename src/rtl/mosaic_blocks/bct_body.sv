`timescale 1ns / 1ps
`default_nettype none

module bct_body #(
    parameter FU_PROFILE = 1,
    // Explicit enables override the legacy profile without coupling peer FUs.
    parameter ENABLE_ALU = 1,
    parameter ENABLE_MULTIPLIER = FU_PROFILE >= 1,
    parameter ENABLE_MAC = FU_PROFILE == 2,
    parameter MULTIPLY_OPERAND_WIDTH = 16,
    parameter ALU_LATENCY = 1,
    parameter MULTIPLY_LATENCY = 1,
    parameter MAC_LATENCY = 1,
    parameter RF_DEPTH = 8,
    parameter RF_READ_PORTS = 2,
    parameter RF_WRITE_PORTS = 1,
    parameter PREDICATE_DEPTH = 2,
    parameter IMMEDIATE_COUNT = 1,
    parameter ACCUMULATOR_COUNT = 1,
    parameter BYPASS_PROFILE = 1,
    parameter REGISTER_BYPASS = 0,
    parameter SYNC_PROFILE = 1,
    parameter RDU_TOTAL_DELAY_ENTRIES = 8,
    parameter INPUT_FIFO_DEPTH = 2,
    parameter RESULT_QUEUE_DEPTH = 2,
    parameter SUPPORT_SPATIAL_TEMPORAL = 1,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter REQUIRE_CANONICAL_NARROW = 1,
    parameter RF_PROTECTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    parameter DATA_WIDTH = 32,
    parameter DATA_METADATA_WIDTH = 32,
    parameter DATA_INPUT_PORTS = 4,
    parameter DATA_OUTPUT_PORTS = 4,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONFIG_WORD_COUNT = 8,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter PREDICATE_METADATA_WIDTH = 16,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    localparam int D = DATA_WIDTH,
    localparam int NI = DATA_INPUT_PORTS,
    localparam int NO = DATA_OUTPUT_PORTS,
    localparam int M = DATA_METADATA_WIDTH,
    localparam int C = CONTEXT_DEPTH,
    localparam int CI = C > 1 ? $clog2(C) : 1,
    localparam int V = CONTEXT_VERSION_WIDTH,
    localparam int W = CONFIG_DATA_WIDTH,
    localparam int N = CONFIG_WORD_COUNT,
    localparam int IM = W * N,
    localparam int PM = PREDICATE_METADATA_WIDTH,
    localparam int P = 1,
    localparam int PI = 1,
    localparam int PO = 1,
    localparam int EI = 1,
    localparam int EO = 1,
    localparam int E = 32,
    localparam int ER = 8,
    localparam int S = 8,
    localparam int RA = RF_DEPTH > 1 ? $clog2(RF_DEPTH) : 1,
    localparam int PA = PREDICATE_DEPTH > 1 ? $clog2(PREDICATE_DEPTH) : 1,
    localparam int AC = ACCUMULATOR_COUNT > 0 ? ACCUMULATOR_COUNT : 1,
    localparam int AA = AC > 1 ? $clog2(AC) : 1,
    localparam int DW = RDU_TOTAL_DELAY_ENTRIES > 0 ? $clog2(RDU_TOTAL_DELAY_ENTRIES + 1) : 1,
    localparam int NS = NI + 2 + IMMEDIATE_COUNT + 2 + AC + 3,
    localparam int SW = $clog2(NS)
) (
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
    // Width-dependent context fields stay local to this parameterized module.
    typedef struct packed {
        logic monitor;
        logic [D*IMMEDIATE_COUNT-1:0] immediates;
        logic [NI*DW-1:0] delays;
        logic invalidate_bypass;
        logic [AC-1:0] invalidate_accumulator;
        logic [AC-1:0] clear_accumulator;
        logic [AC-1:0] required_accumulator;
        logic [PREDICATE_DEPTH-1:0] invalidate_predicate;
        logic [PREDICATE_DEPTH-1:0] required_predicate;
        logic [RF_DEPTH-1:0] invalidate_rf;
        logic [RF_DEPTH-1:0] required_rf;
        logic terminal;
        logic [CI-1:0] next_context;
        logic [1:0] advance_mode;
        logic [15:0] iterations;
        logic trap_overflow;
        logic select_condition;
        logic [2:0] flag_select;
        logic false_token;
        logic predicate_invert;
        logic [PA-1:0] predicate_read;
        logic [1:0] predicate_mode;
        logic write_bypass;
        logic [AA-1:0] accumulator_write;
        logic write_accumulator;
        logic predicate_output;
        logic [PA-1:0] predicate_write;
        logic write_predicate;
        logic [RA-1:0] rf_write;
        logic write_rf;
        logic [NO-1:0] output_mask;
        logic [RA-1:0] rf_read_b;
        logic [RA-1:0] rf_read_a;
        logic [SW-1:0] source_c;
        logic [SW-1:0] source_b;
        logic [SW-1:0] source_a;
        logic saturate;
        logic signed_b;
        logic signed_a;
        logic [4:0] opcode;
        logic [1:0] fu;
        logic [7:0] schema;
    } context_t;

    localparam int RF0 = NI;
    localparam int IMM0 = RF0 + 2;
    localparam int ZERO = IMM0 + IMMEDIATE_COUNT;
    localparam int ONE = ZERO + 1;
    localparam int ACC0 = ONE + 1;
    localparam int BYPASS = ACC0 + AC;
    localparam int PREVIOUS = BYPASS + 1;
    localparam int PREDICATE = PREVIOUS + 1;
    localparam int CW = $bits(context_t);
    localparam int L = (MULTIPLY_LATENCY > MAC_LATENCY ?
        MULTIPLY_LATENCY : MAC_LATENCY) + ALU_LATENCY + REGISTER_BYPASS + 1;
    localparam int PIPE = L > 0 ? L : 1;
    localparam int RF_STRIPES = (D + 255) / 256;
    localparam int RF_LAST = D - (RF_STRIPES - 1) * 256;
    localparam int RC = RF_PROTECTION == 2 ? (RF_STRIPES - 1) * 266 +
        RF_LAST + ecc_pkg::hamming_bits(RF_LAST) + 1 : D + RF_PROTECTION;

    function automatic int capacity(input int channel);
        return RDU_TOTAL_DELAY_ENTRIES / NI +
            int'(channel < RDU_TOTAL_DELAY_ENTRIES % NI);
    endfunction

    function automatic logic [NI*DW-1:0] allocation;
        logic [NI*DW-1:0] value;
        value = '0;
        for (int p = 0; p < NI; p++) value[p*DW+:DW] = DW'(RDU_TOTAL_DELAY_ENTRIES / NI + int'(p
            < RDU_TOTAL_DELAY_ENTRIES % NI));
        return value;
    endfunction

    function automatic bit edge_legal(input int source, input int operand);
        if (source >= NS) return 1'b0;
        if (operand == 2 && ENABLE_MAC == 0) return source == ZERO;
        if (source >= ACC0 && source < BYPASS) return ENABLE_MAC == 1;
        if (source == PREDICATE) return BYPASS_PROFILE == 2;
        if (source == BYPASS || source == PREVIOUS)
            return BYPASS_PROFILE != 0 || ENABLE_MAC == 1;
        return 1'b1;
    endfunction

    function automatic logic [3*NS-1:0] graph;
        logic [3*NS-1:0] value;

        for (int d = 0; d < 3; d++) begin
            for (int s = 0; s < NS; s++) begin
                value[d*NS+s] = 1'b1;

                if (s >= ACC0 && s < BYPASS) value[d*NS+s] = ENABLE_MAC == 1;
                if (s == PREDICATE) value[d*NS+s] = BYPASS_PROFILE == 2;
                if (s == BYPASS || s == PREVIOUS)
                    value[d*NS+s] = BYPASS_PROFILE != 0 || ENABLE_MAC == 1;
                if (d == 2 && ENABLE_MAC == 0) value[d*NS+s] = s == ZERO;
            end
        end
        return value;
    endfunction

    if (CW > IM) begin : g_invalid_layout
        bct_context_image_must_fit invalid_layout ();
    end

    context_t ctx;
    assign ctx = o_body_context_image[CW-1:0];
    wire [NI*DW-1:0] delays = ctx.delays;
    wire [D*IMMEDIATE_COUNT-1:0] immediates = ctx.immediates;
    wire [NO-1:0] outputs = ctx.output_mask;
    wire [RF_DEPTH-1:0] required_rf = ctx.required_rf;
    wire [RF_DEPTH-1:0] invalid_rf = ctx.invalidate_rf;
    wire [PREDICATE_DEPTH-1:0] required_predicate = ctx.required_predicate;
    wire [PREDICATE_DEPTH-1:0] invalid_predicate = ctx.invalidate_predicate;
    wire [AC-1:0] required_accumulator = ctx.required_accumulator;
    wire [AC-1:0] invalid_accumulator = ctx.invalidate_accumulator;
    wire [AC-1:0] clear_accumulator = ctx.clear_accumulator;
    wire [AC-1:0] accumulator_type_signed;
    wire [AC-1:0] accumulator_type_saturate;

    function automatic bit legal_context(input logic [IM-1:0] image);
        context_t c;
        logic [NI*DW-1:0] ds;
        logic [AC-1:0] live_accumulator;
        logic [AC-1:0] cleared_accumulator;
        c = image[CW-1:0];
        ds = c.delays;
        live_accumulator = c.required_accumulator;
        cleared_accumulator = c.clear_accumulator;

        if (c.fu == 2 && c.source_c >= ACC0 && c.source_c < BYPASS)
            live_accumulator = live_accumulator | (AC'(1) << (c.source_c - ACC0));

        legal_context = (^image !== 1'bx) && (image >> CW) == 0 && c.schema == 1 &&
            c.fu <= 2 && (c.fu != 0 || ENABLE_ALU) &&
            (c.fu != 1 || ENABLE_MULTIPLIER) && c.opcode <= 19 && c.flag_select <= 6 &&
            (c.fu == 0 || c.opcode == 0) &&
            (c.fu != 2 || ENABLE_MAC == 1) &&
            (!c.saturate || (SUPPORT_SATURATION == 1 &&
                (c.fu == 2 || (c.fu == 0 && c.opcode < 2)))) &&
            (c.fu != 0 || c.opcode < 18 || SUPPORT_MINMAX == 1) &&
            edge_legal(c.source_a, 0) && edge_legal(c.source_b, 1) &&
            edge_legal(c.source_c, 2) &&
            c.rf_read_a < RF_DEPTH && c.rf_read_b < RF_DEPTH &&
            (!c.write_rf || c.rf_write < RF_DEPTH) &&
            c.predicate_read < PREDICATE_DEPTH &&
            (!c.write_predicate || c.predicate_write < PREDICATE_DEPTH) &&
            (!c.write_accumulator || (ENABLE_MAC == 1 && c.accumulator_write < AC)) &&
            (!c.false_token || (SUPPORT_PREDICATED_TOKEN == 1 && (|c.output_mask))) &&
            ((c.required_rf & c.invalidate_rf) == 0) &&
            ((c.required_predicate & c.invalidate_predicate) == 0) &&
            ((c.required_accumulator & c.invalidate_accumulator) == 0) &&
            ((c.clear_accumulator & c.invalidate_accumulator) == 0) &&
            (ENABLE_MAC == 1 || c.clear_accumulator == 0) &&
            (ENABLE_MAC == 1 || c.required_accumulator == 0) &&
            (!c.write_bypass || BYPASS_PROFILE != 0 || ENABLE_MAC == 1) &&
            (!c.terminal || c.advance_mode == 0) &&
            (c.advance_mode == 0 || (SUPPORT_SPATIAL_TEMPORAL == 1 &&
                c.next_context < C && (c.iterations != 0 || c.advance_mode != 1))) &&
            !(BYPASS_PROFILE == 0 && c.fu == 0 && (c.opcode == 16 || c.opcode == 17) &&
                (c.source_a == RF0 || c.source_a == RF0 + 1) && (|c.output_mask));

        for (int a = 0; a < AC; a++) begin
            if (c.fu == 2 && live_accumulator[a] && accumulator_valid[a] &&
                !cleared_accumulator[a] &&
                (accumulator_type_signed[a] != (c.signed_a || c.signed_b) ||
                accumulator_type_saturate[a] != c.saturate)) legal_context = 1'b0;
        end

        for (int p = 0; p < NI; p++) begin
            if (SYNC_PROFILE == 1) begin
                if (ds[p*DW+:DW] > capacity(p)) legal_context = 1'b0;
            end else if (ds[p*DW+:DW] != 0) legal_context = 1'b0;
        end
    endfunction

    typedef struct packed {
        logic valid;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic legal;
    } validation_t;

    validation_t validation;
    validation_t validation_next;
    wire validation_bad;
    wire validation_corrected;
    assign i_body_validate_ready = !validation.valid || o_body_validate_result_ready;

    always @* begin
        validation_next = validation;

        if (validation.valid && o_body_validate_result_ready) validation_next.valid = 1'b0;
        if (o_body_validate_valid && i_body_validate_ready) begin
            validation_next.valid = 1'b1;
            validation_next.context_id = o_body_validate_context_id;
            validation_next.version = o_body_validate_context_version;
            validation_next.legal = legal_context(o_body_validate_context_image);
        end
    end

    tile_shell_state #(
        .WIDTH($bits(validation_t)), .PROTECTION(CONTROL_PROTECTION)
    ) u_validation (
        .i_clk(i_clk),
        .i_rstb((i_rstb !== 1'b0) &&!o_body_flush),
        .i_enable(validation_next != validation),
        .i_data(validation_next),
        .o_data(validation),
        .o_bad(validation_bad),
        .o_corrected(validation_corrected)
    );

    assign i_body_validate_result_valid = validation.valid &&!validation_bad;
    assign i_body_validate_context_id = validation.context_id;
    assign i_body_validate_context_version = validation.version;
    assign i_body_validate_legal = validation.legal;
    assign i_body_validate_error_code = validation.legal ? 0 : bct_pkg::BCT_ERR_CONTEXT;

    typedef struct packed {
        logic seen;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic started;
        logic completed;
        logic advance;
        logic [15:0] issued;
        logic [15:0] committed;
        logic [31:0] sequence_id;
        logic [RF_DEPTH-1:0] rf_valid;
        logic [ER-1:0] error;
        logic fatal;
    } control_t;

    control_t control;
    control_t control_next;
    wire control_bad;
    wire control_corrected;
    logic [NI-1:0] required_inputs;
    wire integrity_bad;
    wire corrected;
    wire hazard;
    wire count_available;
    wire context_change = o_body_context_active &&!control_bad &&
        i_power_state != tile_shell_pkg::POWER_OFF && (!control.seen ||
        control.context_id != o_body_context_id || control.version != o_body_context_version);
    wire reset_known = i_rstb === 1'b0 || i_rstb === 1'b1;
    wire private_reset = i_rstb !== 1'b0 && i_execution_state != 0;
    wire clear_private = !private_reset || (o_body_flush &&!i_isolate) ||
        i_power_state == tile_shell_pkg::POWER_OFF;
    wire transport_reset = private_reset &&!o_body_flush &&!context_change;
    wire [RF_DEPTH-1:0] rf_valid = control.rf_valid;
    wire running = ((i_execution_state >= 3 && i_execution_state <= 7) ||
        ((i_execution_state == 8 || i_execution_state == 10) && (|required_inputs))) &&
            control.started &&!control.completed &&
        !control.advance && o_body_context_active &&!context_change &&
        !i_isolate && reset_known &&!o_body_flush &&
        control.error == 0 &&!integrity_bad &&!corrected;

    // Context-qualified storage. Only validity/control reset; RF payload does not.
    wire [RF_READ_PORTS*RC-1:0] rf_codes;
    wire [2*D-1:0] rf_reads;
    wire [1:0] rf_bad;
    wire [1:0] rf_corrected;
    wire [1:0] rf_read_enable;
    wire [RC-1:0] rf_write_code;
    wire [D-1:0] commit_data;
    wire commit;
    wire commit_local;
    wire [RA-1:0] commit_rf;
    wire commit_rf_enable;

    register_file #(
        .DATA_WIDTH(RC),
        .DEPTH(RF_DEPTH),
        .NUM_READ_PORTS(RF_READ_PORTS),
        .NUM_WRITE_PORTS(RF_WRITE_PORTS)
    ) u_rf (
        .i_clk(i_clk),
        .i_read_enable(RF_READ_PORTS'(rf_read_enable)),
        .i_read_address((RF_READ_PORTS * RA)'({ctx.rf_read_b, ctx.rf_read_a})),
        .o_read_data(rf_codes),
        .i_write_enable(RF_WRITE_PORTS'(commit_rf_enable)),
        .i_write_address((RF_WRITE_PORTS * RA)'(commit_rf)),
        .i_write_data((RF_WRITE_PORTS * RC)'(rf_write_code))
    );

    tile_shell_codec #(.WIDTH(D), .PROTECTION(RF_PROTECTION)) u_rf_write_codec (
        .i_data(commit_data),
        .o_code(rf_write_code),
        .i_code({RC{1'b0}}),
        .o_data(),
        .o_corrected(),
        .o_bad()
    );

    for (genvar r = 0; r < 2; r++) begin : g_rf_read
        tile_shell_codec #(.WIDTH(D), .PROTECTION(RF_PROTECTION)) u_codec (
            .i_data({D{1'b0}}),
            .o_code(),
            .i_code(rf_codes[r*RC+:RC]),
            .o_data(rf_reads[r*D+:D]),
            .o_corrected(rf_corrected[r]),
            .o_bad(rf_bad[r])
        );
    end

    // The released predicate unit owns predicate writes and readback. Protected
    // witnesses detect corruption in both the data and its independently valid bit.
    wire [PREDICATE_DEPTH-1:0] predicate_data;
    wire [PREDICATE_DEPTH-1:0] predicate_valid;
    wire [PREDICATE_DEPTH-1:0] predicate_bad;
    wire [PREDICATE_DEPTH-1:0] predicate_corrected;
    wire commit_predicate_enable;
    wire [PA-1:0] commit_predicate;
    wire commit_predicate_data;

    for (genvar p = 0; p < PREDICATE_DEPTH; p++) begin : g_predicate
        wire clear_entry = clear_private || (context_change && invalid_predicate[p]);
        wire write_entry = commit_predicate_enable && commit_predicate == p;
        wire raw_data;
        wire raw_valid;
        wire [1:0] protected_value;
        wire bad;

        predicate_unit #(.PRED_DEPTH(1), .NUM_LANES(1), .ASYNC_RESET(ASYNC_RESET)) u_predicate (
            .i_clk(i_clk),
            .i_rstb(!clear_entry),
            .i_clock_enable(1'b1),
            .i_valid(1'b1),
            .i_opcode(write_entry ? predicate_unit_pkg::PRED_LOAD :
                predicate_unit_pkg::PRED_PASS_A),
            .i_lane_mask(1'b1),
            .i_source_a_addr(1'b0),
            .i_source_b_addr(1'b0),
            .i_destination_addr(1'b0),
            .i_predicate_input(commit_predicate_data),
            .i_write_enable(write_entry),
            .o_result(raw_data),
            .o_result_valid(raw_valid),
            .o_valid(),
            .o_any(),
            .o_all(),
            .o_updated_mask(),
            .o_invalidated(),
            .o_illegal_operation()
        );

        tile_shell_state #(.WIDTH(2), .PROTECTION(CONTROL_PROTECTION)) u_witness (
            .i_clk(i_clk),
            .i_rstb(!clear_entry),
            .i_enable(write_entry),
            .i_data({1'b1, commit_predicate_data}),
            .o_data(protected_value),
            .o_bad(bad),
            .o_corrected(predicate_corrected[p])
        );

        assign predicate_data[p] = protected_value[0];
        assign predicate_valid[p] = protected_value[1];
        assign predicate_bad[p] = bad || (raw_valid !== protected_value[1]) ||
            (protected_value[1] && raw_data !== protected_value[0]);
    end

    wire [AC*D-1:0] accumulator_data;
    wire [AC-1:0] accumulator_valid;
    wire [AC-1:0] accumulator_bad;
    wire [AC-1:0] accumulator_corrected;
    wire commit_accumulator_enable;
    wire [AA-1:0] commit_accumulator;

    if (ENABLE_MAC == 1) begin : g_accumulators
        for (genvar a = 0; a < AC; a++) begin : g_entry
            wire clear_entry = clear_private || (context_change && invalid_accumulator[a]);
            wire initialize_entry = context_change && clear_accumulator[a];
            wire write_entry = initialize_entry ||
                (commit_accumulator_enable && commit_accumulator == a);
            wire [D-1:0] raw_data;
            wire raw_valid;
            wire [D+2:0] witness;
            wire raw_signed;
            wire bad;

            accumulator #(.ACC_WIDTH(D), .ASYNC_RESET(ASYNC_RESET)) u_accumulator (
                .i_clk(i_clk),
                .i_rstb(!clear_entry),
                .i_clock_enable(write_entry),
                .i_valid(write_entry),
                .i_command(initialize_entry ? accumulator_pkg::ACC_CLEAR :
                    accumulator_pkg::ACC_LOAD),
                .i_lane_mask(1'b1),
                .i_data(commit_data),
                .i_signed(ctx.signed_a || ctx.signed_b),
                .i_saturate(1'b0),
                .o_data(raw_data),
                .o_state_valid(raw_valid),
                .o_valid(),
                .o_illegal_operation(),
                .o_updated_mask(),
                .o_state_signed(raw_signed),
                .o_carry(),
                .o_borrow(),
                .o_overflow(),
                .o_saturated(),
                .o_zero(),
                .o_negative()
            );

            tile_shell_state #(.WIDTH(D + 3), .PROTECTION(RF_PROTECTION)) u_witness (
                .i_clk(i_clk),
                .i_rstb(!clear_entry),
                .i_enable(write_entry),
                .i_data({ctx.saturate, ctx.signed_a || ctx.signed_b,
                    1'b1, initialize_entry ? {D{1'b0}} : commit_data}),
                .o_data(witness),
                .o_bad(bad),
                .o_corrected(accumulator_corrected[a])
            );
            assign accumulator_data[a*D+:D] = witness[D-1:0];
            assign accumulator_valid[a] = witness[D];
            assign accumulator_type_signed[a] = witness[D+1];
            assign accumulator_type_saturate[a] = witness[D+2];
            assign accumulator_bad[a] = bad || (raw_valid !== witness[D]) ||
                (witness[D] && (raw_data !== witness[D-1:0] || raw_signed !== witness[D+1]));
        end
    end else begin : g_no_accumulator
        assign accumulator_data = '0;
        assign accumulator_valid = '0;
        assign accumulator_type_signed = '0;
        assign accumulator_type_saturate = '0;
        assign accumulator_bad = '0;
        assign accumulator_corrected = '0;
    end

    wire [D:0] bypass_state;
    wire [D:0] previous_state;
    wire bypass_bad;
    wire previous_bad;
    wire bypass_corrected;
    wire previous_corrected;
    wire commit_bypass_enable;

    tile_shell_state #(.WIDTH(D + 1), .PROTECTION(CONTROL_PROTECTION)) u_bypass (
        .i_clk(i_clk),
        .i_rstb(!clear_private &&!(context_change && ctx.invalidate_bypass)),
        .i_enable(commit_bypass_enable),
        .i_data({1'b1, commit_data}),
        .o_data(bypass_state),
        .o_bad(bypass_bad),
        .o_corrected(bypass_corrected)
    );

    tile_shell_state #(.WIDTH(D + 1), .PROTECTION(CONTROL_PROTECTION)) u_previous (
        .i_clk(i_clk),
        .i_rstb(!clear_private &&!(context_change && ctx.invalidate_bypass)),
        .i_enable(commit_local),
        .i_data({1'b1, commit_data}),
        .o_data(previous_state),
        .o_bad(previous_bad),
        .o_corrected(previous_corrected)
    );

    // Synchronizers keep metadata with payload. No associative matching is used.
    wire use_b = ctx.fu != 0 || (ctx.opcode != 5 && ctx.opcode != 16 &&
        (ctx.opcode != 15 ||!ctx.select_condition));
    wire use_a = ctx.fu != 0 || (ctx.opcode != 17 &&
        (ctx.opcode != 15 || ctx.select_condition));
    wire use_c = ctx.fu == 2;

    always @* begin
        required_inputs = '0;
        if (use_a && ctx.source_a < NI) required_inputs[ctx.source_a] = 1'b1;
        if (use_b && ctx.source_b < NI) required_inputs[ctx.source_b] = 1'b1;
        if (use_c && ctx.source_c < NI) required_inputs[ctx.source_c] = 1'b1;
    end

    wire [NI-1:0] synchronized_valid;
    wire [NI*(D+M)-1:0] synchronized_data;
    wire [NI-1:0] synchronized_ready;
    wire [NI-1:0] synchronizer_bad;
    wire [NI-1:0] synchronizer_corrected;
    wire synchronized_empty;
    wire advance;
    wire issue;

    if (SYNC_PROFILE == 2) begin : g_elastic
        wire [NI-1:0] empty;

        for (genvar p = 0; p < NI; p++) begin : g_input
            wire [31:0] occupancy;

            tile_shell_queue #(
                .WIDTH(D + M),
                .DEPTH(INPUT_FIFO_DEPTH),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_fifo (
                .i_clk(i_clk),
                .i_rstb(transport_reset),
                .i_flush(o_body_flush),
                .i_admit(running && required_inputs[p]),
                .i_valid(o_body_data_in_valid[p]),
                .o_ready(i_body_data_in_ready[p]),
                .i_data({o_body_data_in_metadata[p*M+:M], o_body_data_in_payload[p*D+:D]}),
                .i_deliver(1'b1),
                .o_valid(synchronized_valid[p]),
                .i_ready(synchronized_ready[p]),
                .o_data(synchronized_data[p*(D+M)+:(D+M)]),
                .o_count(occupancy),

                .o_bad(synchronizer_bad[p]),
                .o_corrected(synchronizer_corrected[p])
            );

            assign empty[p] = occupancy == 0;
        end

        assign synchronized_empty = &empty;
    end else if (SYNC_PROFILE == 1) begin : g_rdu
        wire [NI*(D+M)-1:0] input_data;
        wire [NI-1:0] empty;
        wire [NI-1:0] errors;
        wire [NI-1:0] rdu_input_valid;

        for (genvar p = 0; p < NI; p++) begin : g_input
            assign input_data[p*(D+M)+:(D+M)] =
                {o_body_data_in_metadata[p*M+:M], o_body_data_in_payload[p*D+:D]};
            assign rdu_input_valid[p] = o_body_data_in_valid[p] && required_inputs[p] &&
                (delays[p*DW+:DW] == 0 || i_body_data_in_ready[p]);
            assign i_body_data_in_ready[p] = running && required_inputs[p] &&
                (delays[p*DW+:DW] == 0 ? issue : advance);
        end

        rdu #(
            .DATA_WIDTH(D + M),
            .NUM_CHANNELS(NI),
            .TOTAL_DELAY_ENTRIES(RDU_TOTAL_DELAY_ENTRIES),
            .CHANNEL_CAPACITY(allocation()),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_rdu (
            .i_clk(i_clk),
            .i_rstb(transport_reset),
            .i_advance(advance),
            .i_channel_enable(required_inputs),
            .i_delay(delays),
            .i_input_data(input_data),
            .i_input_valid(rdu_input_valid),
            .i_flush({NI{o_body_flush}}),
            .o_output_data(synchronized_data),
            .o_output_valid(synchronized_valid),
            .o_output_transfer(),
            .o_channel_empty(empty),
            .o_all_empty(synchronized_empty),
            .o_config_error(errors)
        );

        assign synchronizer_bad = errors;
        assign synchronizer_corrected = '0;
    end else begin : g_aligned
        for (genvar p = 0; p < NI; p++) begin : g_input
            assign synchronized_data[p*(D+M)+:(D+M)] =
                {o_body_data_in_metadata[p*M+:M], o_body_data_in_payload[p*D+:D]};
            assign i_body_data_in_ready[p] = synchronized_ready[p] && running;
        end

        assign synchronized_valid = o_body_data_in_valid;
        assign synchronized_empty = 1'b1;
        assign synchronizer_bad = '0;
        assign synchronizer_corrected = '0;
    end

    wire joined_valid;
    wire [NI-1:0] joined_ready;
    wire [NI*(D+M)-1:0] joined_data;

    stream_join #(.NUM_INPUTS(NI), .DATA_WIDTH(D + M), .HAS_REQUIRED_MASK(1)) u_join (
        .i_valid(synchronized_valid),
        .o_ready(joined_ready),
        .i_data(synchronized_data),
        .i_required(required_inputs),
        .o_valid(joined_valid),
        .i_ready(issue),
        .o_data(joined_data),
        .o_required()
    );

    assign synchronized_ready = joined_ready;

    logic [NS*D-1:0] source_data;
    logic [NS-1:0] source_valid;
    wire [3*D-1:0] operands;
    wire [2:0] operands_valid;
    wire [2:0] selection_error;
    wire [3*SW-1:0] select_bus = {ctx.source_c, ctx.source_b, ctx.source_a};
    wire predicate_available = ctx.predicate_mode != 1 || o_body_predicate_in_valid[0];
    wire predicate_local_available = ctx.predicate_mode != 2 || predicate_valid[ctx.predicate_read];
    wire predicate_value = (ctx.predicate_mode == 0 ? 1'b1 : ctx.predicate_mode == 1 ?
        o_body_predicate_in_payload[0] : ctx.predicate_mode == 2 ?
        predicate_data[ctx.predicate_read] : 1'b0) ^ ctx.predicate_invert;
    assign rf_read_enable[0] = private_reset && o_body_context_active && (ctx.source_a == RF0 ||
        ctx.source_b == RF0 ||
        (use_c && ctx.source_c == RF0)) && rf_valid[ctx.rf_read_a];
    assign rf_read_enable[1] = private_reset && o_body_context_active && (ctx.source_a == RF0 +
        1 || ctx.source_b == RF0 + 1 ||
        (use_c && ctx.source_c == RF0 + 1)) && rf_valid[ctx.rf_read_b];
    always @* begin
        source_data = '0;
        source_valid = '0;

        for (int p = 0; p < NI; p++) begin
            source_data[p*D+:D] = synchronized_data[p*(D+M)+:D];
            source_valid[p] = synchronized_valid[p] &&
                (^synchronized_data[p*(D+M)+:D] !== 1'bx);
        end

        source_data[RF0*D+:2*D] = rf_reads;
        source_valid[RF0] = rf_valid[ctx.rf_read_a] &&!rf_bad[0];
        source_valid[RF0+1] = rf_valid[ctx.rf_read_b] &&!rf_bad[1];

        for (int p = 0; p < IMMEDIATE_COUNT; p++) begin
            source_data[(IMM0+p)*D+:D] = immediates[p*D+:D];
            source_valid[IMM0+p] = 1'b1;
        end

        source_valid[ZERO] = 1'b1;
        source_valid[ONE] = 1'b1;
        source_data[ONE*D+:D] = D'(1);

        for (int a = 0; a < AC; a++) begin
            source_data[(ACC0+a)*D+:D] = accumulator_data[a*D+:D];
            source_valid[ACC0+a] = accumulator_valid[a];
        end

        source_data[BYPASS*D+:D] = bypass_state[D-1:0];
        source_valid[BYPASS] = bypass_state[D];
        source_data[PREVIOUS*D+:D] = previous_state[D-1:0];
        source_valid[PREVIOUS] = previous_state[D];
        source_data[PREDICATE*D+:D] = D'(predicate_data[ctx.predicate_read]);
        source_valid[PREDICATE] = predicate_valid[ctx.predicate_read];
    end

    bypass_network #(
        .DATA_WIDTH(D),
        .NUM_SOURCES(NS),
        .NUM_DESTINATIONS(3),
        .CONNECTIVITY_MASK(graph())
    ) u_sources (
        .i_clk(i_clk),
        .i_rstb(transport_reset),
        .i_source_data(source_data),
        .i_source_valid(source_valid),
        .i_destination_enable({use_c, use_b, use_a} & {3{running}}),
        .i_select(select_bus),
        .i_capture_enable(3'b000),
        .i_flush(o_body_flush),
        .o_destination_data(operands),
        .o_destination_valid(operands_valid),
        .o_selection_error(selection_error)
    );

    wire [D-1:0] a = operands[D-1:0];
    wire [D-1:0] b = operands[D+:D];
    wire [D-1:0] c = operands[2*D+:D];
    wire sources_ready = (!use_a || operands_valid[0]) &&
        (!use_b || operands_valid[1]) && (!use_c || operands_valid[2]) &&
        (!(|required_inputs) || joined_valid) && predicate_available && predicate_local_available;
    wire live_ins_ready = ((rf_valid & required_rf) == required_rf) &&
        ((predicate_valid & required_predicate) == required_predicate) &&
        ((accumulator_valid & required_accumulator) == required_accumulator);
    wire canonical_a = !ctx.signed_a ? (a >> MULTIPLY_OPERAND_WIDTH) == 0 :
        $signed(a) == $signed(D'($signed(a[MULTIPLY_OPERAND_WIDTH-1:0])));
    wire canonical_b = !ctx.signed_b ? (b >> MULTIPLY_OPERAND_WIDTH) == 0 :
        $signed(b) == $signed(D'($signed(b[MULTIPLY_OPERAND_WIDTH-1:0])));
    wire canonical = ctx.fu == 0 || REQUIRE_CANONICAL_NARROW == 0 || (canonical_a && canonical_b);
    wire active_context_legal = legal_context(o_body_context_image);
    wire fu_enable = running && active_context_legal &&!hazard && count_available &&
        advance && i_clock_enable === 1'b1 && sources_ready && live_ins_ready &&
        canonical && predicate_value;
    wire [D-1:0] alu_result;
    wire alu_predicate;
    wire alu_carry;
    wire alu_borrow;
    wire alu_overflow;
    wire alu_saturated;
    wire alu_zero;
    wire alu_negative;
    wire alu_illegal;

    if (ENABLE_ALU) begin : g_alu
        scalar_alu #(
            .DATA_WIDTH(D),
            .SUPPORT_SATURATION(SUPPORT_SATURATION),
            .SUPPORT_MINMAX(SUPPORT_MINMAX)
        ) u_alu (
            .i_enable(fu_enable && ctx.fu == 0),
            .i_opcode(ctx.opcode),
            .i_operand_a(a),
            .i_operand_b(b),
            .i_predicate(ctx.select_condition),
            .i_signed(ctx.signed_a),
            .i_saturate(ctx.saturate),
            .o_result(alu_result),
            .o_predicate(alu_predicate),
            .o_carry(alu_carry),
            .o_borrow(alu_borrow),
            .o_overflow(alu_overflow),
            .o_saturated(alu_saturated),
            .o_zero(alu_zero),
            .o_negative(alu_negative),
            .o_illegal_operation(alu_illegal)
        );
    end else begin : g_no_alu
        assign alu_result = '0;
        assign alu_predicate = '0;
        assign alu_carry = '0;
        assign alu_borrow = '0;
        assign alu_overflow = '0;
        assign alu_saturated = '0;
        assign alu_zero = '0;
        assign alu_negative = '0;
        assign alu_illegal = '0;
    end

    wire [D-1:0] multiply_result;
    wire [D-1:0] mac_result;
    wire mac_overflow;
    wire mac_carry;
    wire mac_saturated;
    wire mac_zero;
    wire mac_negative;
    wire mac_illegal;

    if (ENABLE_MULTIPLIER || ENABLE_MAC) begin : g_multiply
        wire [2*MULTIPLY_OPERAND_WIDTH-1:0] product;
        wire product_signed;

        multiplier #(.OPERAND_WIDTH(MULTIPLY_OPERAND_WIDTH), .LATENCY(0)) u_multiplier (
            .i_clk(i_clk),
            .i_rstb(transport_reset),
            .i_clock_enable(1'b1),
            .i_valid(fu_enable && (ctx.fu == 1 || (ctx.fu == 2 && ctx.signed_a != ctx.signed_b))),
            .i_operand_a(a[MULTIPLY_OPERAND_WIDTH-1:0]),
            .i_operand_b(b[MULTIPLY_OPERAND_WIDTH-1:0]),
            .i_signed_a(ctx.signed_a),
            .i_signed_b(ctx.signed_b),
            .o_product(product),
            .o_product_signed(product_signed),
            .o_valid(),
            .o_zero(),
            .o_negative()
        );

        assign multiply_result = product_signed ? D'($signed(product)) : D'(product);

        if (ENABLE_MAC == 1) begin : g_mac
            wire [D-1:0] same_result;
            wire same_overflow;
            wire same_carry;
            wire same_saturated;
            wire same_zero;
            wire same_negative;
            wire same_illegal;

            mac #(
                .OPERAND_WIDTH(MULTIPLY_OPERAND_WIDTH),
                .ACC_WIDTH(D),
                .LATENCY(0),
                .SUPPORT_SATURATION(SUPPORT_SATURATION)
            ) u_mac (
                .i_clk(i_clk),
                .i_rstb(transport_reset),
                .i_clock_enable(1'b1),
                .i_valid(fu_enable && ctx.fu == 2 && ctx.signed_a == ctx.signed_b),
                .i_operand_a(a[MULTIPLY_OPERAND_WIDTH-1:0]),
                .i_operand_b(b[MULTIPLY_OPERAND_WIDTH-1:0]),
                .i_accumulator(c),
                .i_signed(ctx.signed_a),
                .i_saturate(ctx.saturate),
                .o_result(same_result),
                .o_overflow(same_overflow),
                .o_carry(same_carry),
                .o_saturated(same_saturated),
                .o_zero(same_zero),
                .o_negative(same_negative),
                .o_illegal_operation(same_illegal),
                .o_valid()
            );

            wire [D-1:0] mixed_result;
            wire mixed_overflow;
            wire mixed_carry;
            wire mixed_saturated;
            wire mixed_zero;
            wire mixed_negative;
            wire mixed_illegal;

            // The released MAC has common signedness. Mixed operands compose
            // the exact multiplier with the same scalar final-add semantics.
            scalar_alu #(
                .DATA_WIDTH(D),
                .SUPPORT_SATURATION(SUPPORT_SATURATION)
            ) u_mixed_add (
                .i_enable(fu_enable && ctx.fu == 2 && ctx.signed_a != ctx.signed_b),
                .i_opcode(scalar_alu_pkg::ALU_ADD),
                .i_operand_a(multiply_result),
                .i_operand_b(c),
                .i_predicate(1'b1),
                .i_signed(1'b1),
                .i_saturate(ctx.saturate),
                .o_result(mixed_result),
                .o_overflow(mixed_overflow),
                .o_carry(mixed_carry),
                .o_saturated(mixed_saturated),
                .o_zero(mixed_zero),
                .o_negative(mixed_negative),
                .o_illegal_operation(mixed_illegal),
                .o_predicate(),
                .o_borrow()
            );

            assign mac_result = ctx.signed_a == ctx.signed_b ? same_result : mixed_result;
            assign mac_overflow = ctx.signed_a == ctx.signed_b ? same_overflow : mixed_overflow;
            assign mac_carry = ctx.signed_a == ctx.signed_b ? same_carry : mixed_carry;
            assign mac_saturated = ctx.signed_a == ctx.signed_b ? same_saturated : mixed_saturated;
            assign mac_zero = ctx.signed_a == ctx.signed_b ? same_zero : mixed_zero;
            assign mac_negative = ctx.signed_a == ctx.signed_b ? same_negative : mixed_negative;
            assign mac_illegal = ctx.signed_a == ctx.signed_b ? same_illegal : mixed_illegal;
        end else begin : g_no_mac
            assign mac_result = '0;
            assign mac_overflow = 1'b0;
            assign mac_carry = 1'b0;
            assign mac_saturated = 1'b0;
            assign mac_zero = 1'b0;
            assign mac_negative = 1'b0;
            assign mac_illegal = 1'b0;
        end
    end else begin : g_no_multiply
        assign multiply_result = '0;
        assign mac_result = '0;
        assign mac_overflow = 1'b0;
        assign mac_carry = 1'b0;
        assign mac_saturated = 1'b0;
        assign mac_zero = 1'b0;
        assign mac_negative = 1'b0;
        assign mac_illegal = 1'b0;
    end

    typedef struct packed {
        logic [D-1:0] data;
        logic [M-1:0] metadata;
        logic predicate_value;
        logic false_predicate;
        logic [NO-1:0] output_mask;
        logic rf_write_enable;
        logic [RA-1:0] rf_write_address;
        logic predicate_write_enable;
        logic [PA-1:0] predicate_write_address;
        logic predicate_output;
        logic accumulator_write_enable;
        logic [AA-1:0] accumulator_write_address;
        logic bypass_write_enable;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [OWNER_ID_WIDTH-1:0] owner;
        logic [KERNEL_ID_WIDTH-1:0] kernel;
        logic [31:0] sequence_id;
        logic [6:0] flags;
    } result_t;

    localparam int RW = $bits(result_t);
    result_t result;
    result_t head;
    wire [PIPE-1:0] pipeline_valid;
    wire [RW-1:0] pipeline_data[PIPE];
    wire [PIPE-1:0] pipeline_bad;
    wire [PIPE-1:0] pipeline_corrected;
    wire queue_ready;
    wire queue_valid;
    wire queue_empty;
    wire queue_bad;
    wire queue_corrected;
    wire [31:0] queue_count;
    assign queue_empty = queue_count == 0;
    wire pipeline_empty = !(|pipeline_valid);
    wire transport_empty = pipeline_empty && queue_empty && synchronized_empty;
    wire retiring = (i_execution_state >= 3 && i_execution_state <= 7) || i_execution_state == 8
        || i_execution_state == 10;
    assign advance = queue_ready && retiring && i_clock_enable === 1'b1 &&!i_isolate &&
        !o_body_flush &&!integrity_bad && control.error == 0;
    wire dependency = ctx.source_a >= RF0 && ctx.source_a < RF0 + 2 ||
        ctx.source_b >= RF0 && ctx.source_b < RF0 + 2 ||
        ctx.source_c >= RF0 && ctx.source_c < RF0 + 2 ||
        ctx.source_a >= ACC0 || ctx.source_b >= ACC0 || (use_c && ctx.source_c >= ACC0) ||
        ctx.predicate_mode == 2;
    assign hazard = dependency && (!pipeline_empty ||!queue_empty);
    assign count_available = ctx.iterations == 0 || control.issued < ctx.iterations;
    wire fu_illegal = (ctx.fu == 0 && alu_illegal) || (ctx.fu == 2 && mac_illegal);
    wire overflow = ctx.fu == 0 ? alu_overflow : ctx.fu == 2 ? mac_overflow : 1'b0;
    wire trap = predicate_value && ctx.trap_overflow && overflow;
    assign issue = running && active_context_legal && advance && sources_ready &&
        live_ins_ready && canonical &&
        !hazard && count_available &&
        !fu_illegal &&!trap;
    assign i_body_predicate_in_ready[0] = issue && ctx.predicate_mode == 1;
    // Events are consumed only by the explicit event-driven transition mode.
    assign i_body_event_in_ready[0] = running && ctx.advance_mode == 3 && transport_empty;
    wire [6:0] alu_flags = {alu_saturated, alu_overflow, alu_borrow, alu_carry,
        alu_negative, alu_zero, alu_predicate};
    wire [6:0] mac_flags = {mac_saturated, mac_overflow, 1'b0, mac_carry,
        mac_negative, mac_zero, 1'b0};
    logic [M-1:0] issue_metadata;

    always @* begin
        issue_metadata = (M'(o_body_context_version) << CI) | M'(o_body_context_id);

        for (int p = NI - 1; p >= 0; p--) begin
            if (required_inputs[p]) issue_metadata = synchronized_data[p*(D+M)+D+:M];
        end

        // One body-owned bit records false-token status without changing shell identity.
        if (!predicate_value) issue_metadata = issue_metadata | (M'(1) << (CI + V));

        result = '0;
        result.data = !predicate_value ? '0 : ctx.fu == 0 ? alu_result :
            ctx.fu == 1 ? multiply_result : mac_result;
        result.flags = ctx.fu == 0 ? alu_flags : ctx.fu == 2 ? mac_flags :
            {4'b0, result.data[D-1], result.data == 0, 1'b0};

        case (ctx.flag_select)
            0: result.predicate_value = result.flags[0];
            1: result.predicate_value = result.flags[1];
            2: result.predicate_value = result.flags[2];
            3: result.predicate_value = result.flags[3];
            4: result.predicate_value = result.flags[4];
            5: result.predicate_value = result.flags[5];
            6: result.predicate_value = result.flags[6];
            default: result.predicate_value = 1'b0;
        endcase

        result.false_predicate = !predicate_value;
        result.output_mask = predicate_value || ctx.false_token ? outputs : '0;
        result.metadata = issue_metadata;
        result.rf_write_enable = ctx.write_rf && predicate_value;
        result.rf_write_address = ctx.rf_write;
        result.predicate_write_enable = ctx.write_predicate && predicate_value;
        result.predicate_write_address = ctx.predicate_write;
        result.predicate_output = ctx.predicate_output && predicate_value;
        result.accumulator_write_enable = ctx.write_accumulator && predicate_value;
        result.accumulator_write_address = ctx.accumulator_write;
        result.bypass_write_enable = ctx.write_bypass && predicate_value;
        result.context_id = o_body_context_id;
        result.version = o_body_context_version;
        result.owner = i_owner;
        result.kernel = i_kernel;
        result.sequence_id = control.sequence_id;
    end

    wire [6:0] head_flags = head.flags;
    wire [NO-1:0] head_outputs = head.output_mask;
    wire ownership_ok = head.context_id == o_body_context_id &&
        head.version == o_body_context_version && head.owner == i_owner && head.kernel == i_kernel;
    wire destinations_ready = ((o_body_data_out_ready & head_outputs) == head_outputs) &&
        (!head.predicate_output || o_body_predicate_out_ready[0] === 1'b1);
    assign commit = queue_valid && active_context_legal && destinations_ready &&
        ownership_ok && retiring &&
        i_clock_enable === 1'b1 &&!i_isolate &&!o_body_flush &&!integrity_bad && control.error == 0;
    assign commit_local = commit &&!head.false_predicate;
    assign commit_data = head.data;
    assign commit_rf_enable = commit_local && head.rf_write_enable;
    assign commit_rf = head.rf_write_address;
    assign commit_predicate_enable = commit_local && head.predicate_write_enable;
    assign commit_predicate = head.predicate_write_address;
    assign commit_predicate_data = head.predicate_value;
    assign commit_accumulator_enable = commit_local && head.accumulator_write_enable;
    assign commit_accumulator = head.accumulator_write_address;
    assign commit_bypass_enable = commit_local && head.bypass_write_enable;

    // Admission into the shell's independently buffered outputs is one atomic
    // transaction. External consumers may subsequently retire each copy separately.
    for (genvar p = 0; p < NO; p++) begin : g_output
        assign i_body_data_out_valid[p] = commit && head_outputs[p];
        assign i_body_data_out_payload[p*D+:D] = i_body_data_out_valid[p] ? head.data : '0;
        assign i_body_data_out_metadata[p*M+:M] = queue_valid ? head.metadata : '0;
    end

    assign i_body_predicate_out_valid[0] = commit && head.predicate_output;
    assign i_body_predicate_out_payload[0] = i_body_predicate_out_valid[0] && head.predicate_value;
    assign i_body_predicate_out_metadata = queue_valid ? PM'(head.context_id) : '0;
    assign i_body_event_out_valid = '0;
    assign i_body_event_out_payload = '0;

    wire [31:0] selected_latency = ctx.fu == 0 ? ALU_LATENCY :
        ctx.fu == 1 ? MULTIPLY_LATENCY : MAC_LATENCY;
    wire source_registered = REGISTER_BYPASS == 1 &&
        (ctx.source_a == BYPASS || ctx.source_b == BYPASS || (use_c && ctx.source_c == BYPASS));
    wire [31:0] latency = selected_latency + int'(source_registered);

    for (genvar p = 0; p < PIPE; p++) begin : g_pipeline
        wire incoming_valid;

        if (p < PIPE - 1) begin : g_valid_next
            assign incoming_valid = (issue && latency == p + 1) || pipeline_valid[p+1];
        end else begin : g_valid_last
            assign incoming_valid = issue && latency == p + 1;
        end

        wire [RW-1:0] incoming_data;

        if (p < PIPE - 1) begin : g_next
            assign incoming_data = issue && latency == p + 1 ? result : pipeline_data[p+1];
        end else begin : g_last
            assign incoming_data = result;
        end

        tile_shell_state #(.WIDTH(RW + 1), .PROTECTION(CONTROL_PROTECTION)) u_stage (
            .i_clk(i_clk),
            .i_rstb(transport_reset),
            .i_enable(advance),
            .i_data({incoming_valid, incoming_data}),
            .o_data({pipeline_valid[p], pipeline_data[p]}),
            .o_bad(pipeline_bad[p]),
            .o_corrected(pipeline_corrected[p])
        );
    end

    tile_shell_queue #(.WIDTH(RW), .DEPTH(RESULT_QUEUE_DEPTH),
        .PROTECTION(CONTROL_PROTECTION)) u_results (
        .i_clk(i_clk),
        .i_rstb(transport_reset),
        .i_flush(o_body_flush),
        .i_admit(retiring && i_clock_enable === 1'b1 &&!i_isolate &&!integrity_bad),
        .i_valid((latency == 0 && issue) || (advance && pipeline_valid[0])),
        .o_ready(queue_ready),
        .i_data(latency == 0 && issue ? result : pipeline_data[0]),
        .i_deliver(1'b1),
        .o_valid(queue_valid),
        .i_ready(commit),
        .o_data(head),
        .o_count(queue_count),

        .o_bad(queue_bad),
        .o_corrected(queue_corrected)
    );

    assign integrity_bad = control_bad || validation_bad || bypass_bad || previous_bad ||
        (|predicate_bad) || (|accumulator_bad) || (|pipeline_bad) || queue_bad ||
        (|synchronizer_bad) || (|(rf_bad & rf_read_enable));
    assign corrected = control_corrected || validation_corrected || bypass_corrected ||
        previous_corrected || (|predicate_corrected) || (|accumulator_corrected) ||
        (|pipeline_corrected) || queue_corrected || (|synchronizer_corrected) ||
        (|(rf_corrected & rf_read_enable));
    wire runtime_source_error = running &&!hazard && sources_ready &&!canonical;
    wire local_source_missing = running &&!hazard &&
        (!(|required_inputs) || joined_valid) && predicate_available &&
        (!predicate_local_available ||!live_ins_ready ||
        (use_a && ctx.source_a >= NI &&!operands_valid[0]) ||
        (use_b && ctx.source_b >= NI &&!operands_valid[1]) ||
        (use_c && ctx.source_c >= NI &&!operands_valid[2]));
    wire runtime_schedule_error = SYNC_PROFILE != 2 && local_source_missing;
    wire runtime_context_error = running &&!active_context_legal;
    wire runtime_trap = running && sources_ready &&!hazard && trap;

    always @* begin
        control_next = control;

        if (context_change) begin
            control_next.seen = 1'b1;
            control_next.context_id = o_body_context_id;
            control_next.version = o_body_context_version;
            control_next.issued = '0;
            control_next.committed = '0;
            control_next.completed = 1'b0;
            control_next.advance = 1'b0;
            control_next.rf_valid = rf_valid & ~invalid_rf;
            control_next.started = (i_execution_state >= 3 && i_execution_state <= 7);
        end

        if (o_body_start || o_body_resume) control_next.started = 1'b1;

        if (issue) begin
            control_next.issued = control.issued + 1'b1;
            control_next.sequence_id = control.sequence_id + 1'b1;
        end

        if (commit) begin
            control_next.committed = control.committed + 1'b1;

            if (commit_rf_enable) control_next.rf_valid = rf_valid | (RF_DEPTH'(1) << commit_rf);

            if (ctx.iterations != 0 && control.committed + 1'b1 == ctx.iterations) begin
                if (ctx.advance_mode == 1) control_next.advance = 1'b1;
                else if (ctx.terminal) control_next.completed = 1'b1;
            end

            if (ctx.advance_mode == 2 &&!head.false_predicate && head.predicate_value)
                control_next.advance = 1'b1;
        end

        if (o_body_event_in_valid[0] && i_body_event_in_ready[0]) control_next.advance = 1'b1;

        if (o_advance_valid && i_advance_ready) begin
            control_next.advance = 1'b0;
            control_next.seen = 1'b0;
        end

        if (integrity_bad || (queue_valid &&!ownership_ok)) begin
            control_next.error = integrity_bad ? bct_pkg::BCT_ERR_INTEGRITY :
                bct_pkg::BCT_ERR_OWNERSHIP;
            control_next.fatal = 1'b1;
        end else if (runtime_context_error) control_next.error = bct_pkg::BCT_ERR_CONTEXT;
        else if (runtime_source_error) control_next.error = bct_pkg::BCT_ERR_CANONICAL;
        else if (runtime_schedule_error) control_next.error = bct_pkg::BCT_ERR_SOURCE;
        else if (runtime_trap) control_next.error = bct_pkg::BCT_ERR_OVERFLOW;

        if (clear_private) control_next = '0;
    end

    tile_shell_state #(.WIDTH($bits(control_t)), .PROTECTION(CONTROL_PROTECTION)) u_control (
        .i_clk(i_clk),
        .i_rstb(private_reset),
        .i_enable(reset_known && control_next != control),
        .i_data(control_next),
        .o_data(control),
        .o_bad(control_bad),
        .o_corrected(control_corrected)
    );

    assign o_advance_valid = control.advance && transport_empty &&!control.fatal;
    assign o_advance_context = ctx.next_context;
    assign i_body_completed = control.completed && transport_empty &&!control.fatal;
    assign i_body_safe_point = transport_empty &&!context_change;
    assign i_body_drain_done = transport_empty;
    assign i_body_idle = transport_empty;
    assign i_body_busy = !transport_empty;
    assign i_body_stall_reasons = {4'b0, running &&!sources_ready,
        1'b0, queue_valid &&!destinations_ready, running && (!sources_ready ||!live_ins_ready)};
    assign i_body_error = corrected || control.error != 0 || runtime_source_error ||
        runtime_context_error || runtime_schedule_error || runtime_trap;

    // Register detected faults independently from the potentially corrupt record.
    // This also avoids feeding healthy-qualified shell readback into its own
    // asynchronous containment decision. Issue/commit already fail closed.
    wire fatal_latched;
    wire fault_bad;

    tile_shell_state #(.WIDTH(1), .PROTECTION(CONTROL_PROTECTION)) u_fault (
        .i_clk(i_clk),
        .i_rstb((i_rstb !== 1'b0) &&!clear_private),
        .i_enable(reset_known && (integrity_bad || (queue_valid &&!ownership_ok))),
        .i_data(1'b1),
        .o_data(fatal_latched),
        .o_bad(fault_bad),
        .o_corrected()
    );

    assign i_body_fatal_error = control.fatal || fatal_latched || fault_bad;
    assign i_body_error_code = corrected ? bct_pkg::BCT_ERR_CORRECTED : integrity_bad ?
        bct_pkg::BCT_ERR_INTEGRITY :
        runtime_source_error ? bct_pkg::BCT_ERR_CANONICAL :
        runtime_context_error ? bct_pkg::BCT_ERR_CONTEXT :
        runtime_schedule_error ? bct_pkg::BCT_ERR_SOURCE :
        runtime_trap ? bct_pkg::BCT_ERR_OVERFLOW : control.error;
    assign i_body_wakeup_required = !transport_empty || (o_body_context_active &&
        (o_body_validate_valid || (|o_body_data_in_valid) || (|o_body_predicate_in_valid)));
    // Counters observe real issue/commit edges; no counter controls execution.
    logic [32*8-1:0] event_increment;
    logic [32*5-1:0] event_select;

    always @* begin
        event_increment = '0;
        event_select = '0;

        for (int e = 0; e < 32; e++) event_select[e*5+:5] = 5'(e);

        event_increment[0*8+:8] = 8'(issue);
        event_increment[1*8+:8] = 8'(commit);
        event_increment[2*8+:8] = 8'(issue && ctx.fu == 0);
        event_increment[3*8+:8] = 8'(issue && ctx.fu == 1);
        event_increment[4*8+:8] = 8'(issue && ctx.fu == 2);
        event_increment[5*8+:8] = issue ? 8'($countones(rf_read_enable)) : 0;
        event_increment[6*8+:8] = 8'(commit_rf_enable);
        event_increment[7*8+:8] = 8'(running &&!live_ins_ready);
        event_increment[8*8+:8] = 8'(issue && ctx.predicate_mode != 0);
        event_increment[9*8+:8] = 8'(commit_predicate_enable);
        event_increment[10*8+:8] = 8'(issue &&!predicate_value &&!ctx.false_token);
        event_increment[11*8+:8] = 8'(issue &&!predicate_value && ctx.false_token);
        event_increment[12*8+:8] = 8'(issue && (ctx.source_a == BYPASS || ctx.source_b == BYPASS));
        event_increment[13*8+:8] = 8'(commit_bypass_enable);
        event_increment[14*8+:8] = 8'(SYNC_PROFILE == 1 && advance);
        event_increment[15*8+:8] = 8'(SYNC_PROFILE == 1 && running &&!sources_ready);
        event_increment[16*8+:8] = 8'(SYNC_PROFILE == 2 && running &&!joined_valid);
        event_increment[17*8+:8] = 8'(running &&!sources_ready);
        event_increment[18*8+:8] = 8'(queue_valid &&!destinations_ready);
        event_increment[19*8+:8] = 8'(context_change);
        event_increment[20*8+:8] = 8'(o_advance_valid && i_advance_ready);
        event_increment[21*8+:8] = 8'(issue && overflow);
        event_increment[22*8+:8] = 8'(issue && result.flags[6]);
        event_increment[23*8+:8] = 8'(runtime_source_error);
        event_increment[24*8+:8] = 8'(i_body_error || i_body_fatal_error);
        event_increment[25*8+:8] = 8'(i_body_idle);
        event_increment[26*8+:8] = 8'(i_clock_enable);
        event_increment[27*8+:8] = 8'(!i_clock_enable);
        event_increment[28*8+:8] = 8'($countones(o_body_data_in_valid & i_body_data_in_ready));
        event_increment[29*8+:8] = 8'($countones(i_body_data_out_valid & o_body_data_out_ready));
        event_increment[30*8+:8] = 8'(i_body_predicate_out_valid[0] &&
            o_body_predicate_out_ready[0]);
        event_increment[31*8+:8] = 8'(i_body_completed);
    end

    performance_counters #(
        .COUNTER_WIDTH(32),
        .NUM_COUNTERS(32),
        .NUM_EVENTS(32),
        .INCREMENT_WIDTH(8),
        .HAS_SNAPSHOT(0),
        .HAS_THRESHOLD(0),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_counters (
        .i_clk(i_clk),
        .i_rstb(private_reset &&!clear_private),
        .i_global_enable(i_monitor_enable && ctx.monitor),
        .i_freeze(1'b0),
        .i_counter_enable(32'hffffffff),
        .i_clear(32'b0),
        .i_event_select(event_select),
        .i_event_valid(32'hffffffff),
        .i_event_increment(event_increment),
        .i_threshold_enable(32'b0),
        .i_threshold_value(1024'b0),
        .i_snapshot(1'b0),
        .i_read_enable(1'b1),
        .i_read_snapshot(1'b0),
        .i_read_index(i_counter_index),
        .o_read_data(o_counter_data),
        .o_read_overflow(),
        .o_read_valid(),
        .o_counter_overflow(),
        .o_threshold_event(),
        .o_config_error(),
        .o_snapshot_valid()
    );
endmodule
`default_nettype wire
