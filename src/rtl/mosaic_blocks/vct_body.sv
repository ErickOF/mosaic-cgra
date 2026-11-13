`timescale 1ns / 1ps
`default_nettype none

// Single-issue vector body with explicit protected ownership and atomic commit.
module vct_body #(
    parameter NUM_LANES = 4,
    parameter ELEMENT_WIDTH = 8,
    parameter ACC_WIDTH = 32,
    parameter FU_PROFILE = 1,
    // Explicit enables override the legacy profile without coupling peer FUs.
    parameter ENABLE_LANE_ALU = 1,
    parameter ENABLE_REDUCTION = FU_PROFILE >= 1,
    parameter ENABLE_DOT_PRODUCT = FU_PROFILE == 2,
    parameter LANE_LATENCY = 1,
    parameter MUL_LATENCY = 1,
    parameter MAC_LATENCY = 1,
    parameter REDUCTION_LATENCY = 1,
    parameter DOT_LATENCY = 2,
    parameter VRF_DEPTH = 8,
    parameter VRF_READ_PORTS = 2,
    parameter VRF_WRITE_PORTS = 1,
    parameter WRITE_SLICE_WIDTH = 8,
    parameter PREDICATE_DEPTH = 4,
    parameter VECTOR_ACC_DEPTH = 2,
    parameter SCALAR_ACC_DEPTH = 2,
    parameter BYPASS_PROFILE = 1,
    parameter REGISTER_BYPASS = 0,
    parameter SYNC_PROFILE = 1,
    parameter RDU_TOTAL_DELAY_ENTRIES = 8,
    parameter INPUT_FIFO_DEPTH = 2,
    parameter RESULT_QUEUE_DEPTH = 2,
    parameter SUPPORT_SPATIAL_TEMPORAL = 1,
    parameter SUPPORT_MUL = 1,
    parameter SUPPORT_MAC = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter SUPPORT_BROADCAST = 1,
    parameter SUPPORT_LANE_SELECT = 1,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter REQUIRE_CANONICAL_FORMAT = 1,
    parameter VRF_PROTECTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    parameter DATA_METADATA_WIDTH = 64,
    parameter DATA_INPUT_PORTS = 2,
    parameter DATA_OUTPUT_PORTS = 2,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONFIG_WORD_COUNT = 32,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter PREDICATE_METADATA_WIDTH = 16,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    localparam int LN = NUM_LANES,
    localparam int EL = ELEMENT_WIDTH,
    localparam int A = ACC_WIDTH,
    localparam int D = LN * A,
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
    localparam int P = LN,
    localparam int PI = 1,
    localparam int PO = 1,
    localparam int EI = 1,
    localparam int EO = 1,
    localparam int E = 32,
    localparam int ER = 8,
    localparam int S = 8,
    localparam int RA = VRF_DEPTH > 1 ? $clog2(VRF_DEPTH) : 1,
    localparam int PA = PREDICATE_DEPTH > 1 ? $clog2(PREDICATE_DEPTH) : 1,
    localparam int VA = VECTOR_ACC_DEPTH > 1 ? $clog2(VECTOR_ACC_DEPTH) : 1,
    localparam int CA = SCALAR_ACC_DEPTH > 1 ? $clog2(SCALAR_ACC_DEPTH) : 1,
    localparam int SP = A / WRITE_SLICE_WIDTH,
    localparam int SM = LN * SP,
    localparam int SA = SP > 1 ? $clog2(SP) : 1,
    localparam int LI = $clog2(LN),
    localparam int DW = RDU_TOTAL_DELAY_ENTRIES > 0 ? $clog2(RDU_TOTAL_DELAY_ENTRIES + 1) : 1,
    localparam int NS = NI + 8,
    localparam int SW = $clog2(NS)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic [NI*D-1:0] i_raw_data_payload,
    input logic [NI*M-1:0] i_raw_data_metadata,
    output logic [NI*D-1:0] o_isolated_data_payload,
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
    import vct_pkg::*;

    typedef struct packed {
        logic [LN-1:0] invalidate_mask;
        logic [LN-1:0] required_mask;
        logic local_mask;
        logic [SCALAR_ACC_DEPTH-1:0] required_sacc;
        logic [VECTOR_ACC_DEPTH*LN-1:0] required_vacc;
        logic [PREDICATE_DEPTH*LN-1:0] required_predicate;
        logic monitor;
        logic [D-1:0] immediate;
        logic [NI*DW-1:0] delays;
        logic invalidate_bypass;
        logic [SCALAR_ACC_DEPTH-1:0] invalidate_sacc;
        logic [SCALAR_ACC_DEPTH-1:0] clear_sacc;
        logic [VECTOR_ACC_DEPTH*LN-1:0] invalidate_vacc;
        logic [VECTOR_ACC_DEPTH*LN-1:0] clear_vacc;
        logic [PREDICATE_DEPTH*LN-1:0] invalidate_predicate;
        logic [VRF_DEPTH*SM-1:0] invalidate_rf;
        logic [VRF_DEPTH*SM-1:0] required_rf;
        logic terminal;
        logic [CI-1:0] next_context;
        logic [1:0] advance_mode;
        logic [15:0] iterations;
        logic trap_overflow;
        logic accumulate;
        logic write_bypass;
        logic [CA-1:0] sacc_write;
        logic write_sacc;
        logic [VA-1:0] vacc_write;
        logic write_vacc;
        logic write_mask;
        logic predicate_output;
        logic [PA-1:0] predicate_write;
        logic write_predicate;
        logic [SM-1:0] slice_mask;
        logic [SA-1:0] write_slice;
        logic [RA-1:0] rf_write;
        logic write_rf;
        logic [NO-1:0] output_mask;
        logic [LI-1:0] extract_lane;
        logic [LN-1:0] select_mask;
        logic false_token;
        logic predicate_invert;
        logic [PA-1:0] predicate_read;
        logic [1:0] predicate_mode;
        logic [LN-1:0] runtime_tail;
        logic tail_mask;
        logic metadata_mask;
        logic [LN-1:0] lane_mask;
        logic [SA-1:0] read_slice_b;
        logic [SA-1:0] read_slice_a;
        logic [RA-1:0] rf_read_b;
        logic [RA-1:0] rf_read_a;
        logic [SW-1:0] source_c;
        logic [SW-1:0] source_b;
        logic [SW-1:0] source_a;
        logic [2:0] result_format;
        logic [2:0] format_c;
        logic [2:0] format_b;
        logic [2:0] format_a;
        logic saturate;
        logic signed_mode;
        logic [4:0] opcode;
        logic [2:0] fu;
        logic [7:0] schema;
    } context_t;

    localparam int RF0 = NI;
    localparam int RF1 = NI + 1;
    localparam int IMM = NI + 2;
    localparam int ZERO = NI + 3;
    localparam int VACC = NI + 4;
    localparam int SACC = NI + 5;
    localparam int BYPASS = NI + 6;
    localparam int PREVIOUS = NI + 7;
    localparam int MB = CI + V;
    localparam int CW = $bits(context_t);
    context_t ctx;
    assign ctx = o_body_context_image[CW-1:0];

    if (CW > IM) begin : g_invalid_layout
        vct_context_image_must_fit invalid_layout ();
    end

    function automatic int format_width(input logic [2:0] f);
        case (f)
            VCT_ELEMENT_VECTOR: return LN * EL;
            VCT_PRODUCT_VECTOR: return LN * 2 * EL;
            VCT_ACC_VECTOR: return D;
            VCT_SCALAR_ELEMENT: return EL;
            VCT_SCALAR_ACC: return A;
            default: return 0;
        endcase
    endfunction

    function automatic int lane_width(input logic [2:0] f);
        case (f)
            VCT_ELEMENT_VECTOR, VCT_SCALAR_ELEMENT: return EL;
            VCT_PRODUCT_VECTOR: return 2 * EL;
            VCT_ACC_VECTOR, VCT_SCALAR_ACC: return A;
            default: return 0;
        endcase
    endfunction

    // Isolate provably inactive input lanes before protected shell buffering.
    // Padding remains observable, so illegal noncanonical inputs cannot be hidden.
    logic [LN-1:0] ingress_mask;
    logic [2:0] ingress_format;

    always @* begin
        o_isolated_data_payload = i_raw_data_payload;
        ingress_mask = '0;
        ingress_format = '0;

        for (int p = 0; p < NI; p++) begin
            ingress_mask = ctx.lane_mask;
            ingress_format = i_raw_data_metadata[p*M+MB+:3];

            if (ctx.metadata_mask)
                ingress_mask = ingress_mask & i_raw_data_metadata[p*M+MB+3+:LN];

            if (ctx.tail_mask) ingress_mask = ingress_mask & ctx.runtime_tail &
                i_raw_data_metadata[p*M+MB+4+LN+:LN];

            if (ctx.predicate_mode == VCT_PRED_NEVER &&!ctx.predicate_invert)
                ingress_mask = '0;

            for (int bit_index = 0; bit_index < D; bit_index++) begin
                if (ingress_format < 3 && bit_index < format_width(ingress_format) &&
                    ingress_mask[bit_index / lane_width(ingress_format)] === 1'b0)
                    o_isolated_data_payload[p*D+bit_index] = 1'b0;
            end
        end
    end

    function automatic bit edge_legal(input int source, input int operand);
        if (source < 0 || source >= NS) return 1'b0;

        if (source == SACC && !(ENABLE_REDUCTION || ENABLE_DOT_PRODUCT)) return 1'b0;

        if (BYPASS_PROFILE == 0 && (source == RF0 || source == RF1 ||
            source == SACC && operand != 2))
            return 1'b0;

        if (operand == 2) return source == VACC || source == SACC || source == ZERO ||
            (BYPASS_PROFILE == 2 && source < NI);

        if (source == RF0) return operand == 0;

        if (source == RF1) return operand == 1;

        if (source == SACC) return BYPASS_PROFILE == 2;

        return 1'b1;
    endfunction

    function automatic logic [3*NS-1:0] graph;
        logic [3*NS-1:0] value;

        for (int d = 0; d < 3; d++) begin
            for (int s = 0; s < NS; s++) begin
                value[d*NS+s] = 1'b1;
                if (s == SACC && !(ENABLE_REDUCTION || ENABLE_DOT_PRODUCT)) value[d*NS+s] = 1'b0;

                if (BYPASS_PROFILE == 0 && (s == RF0 || s == RF1 || s == SACC && d != 2))
                    value[d*NS+s] = 1'b0;

                if (s == RF0 && d != 0) value[d*NS+s] = 1'b0;

                if (s == RF1 && d != 1) value[d*NS+s] = 1'b0;

                if (s == SACC && d != 2 && BYPASS_PROFILE != 2) value[d*NS+s] = 1'b0;

                if (d == 2 && s != VACC && s != SACC && s != ZERO &&
                    !(BYPASS_PROFILE == 2 && s < NI)) value[d*NS+s] = 1'b0;
            end
        end

        return value;
    endfunction

    function automatic logic [NI*DW-1:0] allocation;
        logic [NI*DW-1:0] value;

        for (int p = 0; p < NI; p++)
            value[p*DW+:DW] = DW'(RDU_TOTAL_DELAY_ENTRIES / NI +
                int'(p < RDU_TOTAL_DELAY_ENTRIES % NI));
        return value;
    endfunction

    function automatic bit legal_context(input logic [IM-1:0] image);
        context_t c;
        logic [NI*DW-1:0] ds;
        logic [SM-1:0] selected_slices;
        int expected;
        int slices;
        c = image[CW-1:0];
        ds = c.delays;
        selected_slices = c.slice_mask;
        expected = c.result_format;
        slices = lane_width(c.result_format) / WRITE_SLICE_WIDTH;

        if (^image === 1'bx || image >> CW != 0 || c.schema != 1 || c.fu > VCT_PASS)
            return 1'b0;

        if (c.fu >= VCT_DOT && c.opcode != 0) return 1'b0;

        if (c.format_a > 4 || c.format_b > 4 || c.format_c > 4 || c.result_format > 4)
            return 1'b0;

        if (!edge_legal(c.source_a, 0) ||!edge_legal(c.source_b, 1) ||
            !edge_legal(c.source_c, 2)) return 1'b0;

        if (c.rf_read_a >= VRF_DEPTH || c.rf_read_b >= VRF_DEPTH ||
            c.rf_write >= VRF_DEPTH || c.predicate_read >= PREDICATE_DEPTH ||
            c.predicate_write >= PREDICATE_DEPTH || c.vacc_write >= VECTOR_ACC_DEPTH ||
            c.sacc_write >= SCALAR_ACC_DEPTH || c.extract_lane >= LN || c.next_context >= C)
            return 1'b0;

        if ((c.required_predicate & c.invalidate_predicate) != 0 ||
            (c.required_vacc & c.invalidate_vacc) != 0 ||
            (c.required_sacc & c.invalidate_sacc) != 0 ||
            (c.required_mask & c.invalidate_mask) != 0) return 1'b0;

        if ((c.required_rf & c.invalidate_rf) != 0 ||
            (c.clear_vacc & c.invalidate_vacc) != 0 ||
            (c.clear_sacc & c.invalidate_sacc) != 0) return 1'b0;

        if (c.saturate && SUPPORT_SATURATION == 0 || c.false_token &&
            SUPPORT_PREDICATED_TOKEN == 0 || c.advance_mode != 0 &&
            SUPPORT_SPATIAL_TEMPORAL == 0) return 1'b0;

        if (c.fu == VCT_LANE) begin
            if (c.opcode < 20 &&!ENABLE_LANE_ALU || c.opcode > 21 ||
                c.opcode == 20 && SUPPORT_MUL == 0 ||
                c.opcode == 21 && SUPPORT_MAC == 0 ||
                (c.opcode == 18 || c.opcode == 19) && SUPPORT_MINMAX == 0)
                return 1'b0;

            if (c.format_a != VCT_ELEMENT_VECTOR || c.format_b != VCT_ELEMENT_VECTOR)
                return 1'b0;

            if (c.opcode == 21 && c.format_c != VCT_ACC_VECTOR) return 1'b0;
            expected = c.opcode == 20 ? VCT_PRODUCT_VECTOR :
                c.opcode == 21 ? VCT_ACC_VECTOR : VCT_ELEMENT_VECTOR;
        end

        if (c.fu == VCT_REDUCTION) begin
            if (!ENABLE_REDUCTION || c.opcode > 4 || c.format_a != VCT_ELEMENT_VECTOR ||
                (c.opcode == 1 || c.opcode == 2) &&
                (SUPPORT_MINMAX == 0 || c.lane_mask == 0)) return 1'b0;

            expected = c.opcode == 0 ? VCT_SCALAR_ACC : VCT_SCALAR_ELEMENT;
        end

        if (c.fu == VCT_DOT) begin
            if (!ENABLE_DOT_PRODUCT || c.format_a != VCT_ELEMENT_VECTOR ||
                c.format_b != VCT_ELEMENT_VECTOR) return 1'b0;

            expected = VCT_SCALAR_ACC;
        end

        if (c.fu == VCT_BROADCAST) begin
            if (SUPPORT_BROADCAST == 0 ||
                (c.format_a != VCT_SCALAR_ELEMENT && c.format_a != VCT_SCALAR_ACC))

                return 1'b0;

            expected = c.format_a == VCT_SCALAR_ELEMENT ? VCT_ELEMENT_VECTOR : VCT_ACC_VECTOR;
        end

        if (c.fu == VCT_EXTRACT) begin
            if (SUPPORT_LANE_SELECT == 0 || c.format_a > VCT_ACC_VECTOR) return 1'b0;

            expected = c.format_a == VCT_ELEMENT_VECTOR ? VCT_SCALAR_ELEMENT : VCT_SCALAR_ACC;
        end

        if (c.fu == VCT_PASS) expected = c.format_a;

        if (c.result_format != expected) return 1'b0;

        if (c.fu == VCT_LANE && c.saturate && c.opcode != 0 && c.opcode != 1 &&
            c.opcode != 21) return 1'b0;

        if (c.source_a == VACC && c.format_a != VCT_ACC_VECTOR ||
            c.source_b == VACC && c.format_b != VCT_ACC_VECTOR ||
            c.source_c == VACC && c.format_c != VCT_ACC_VECTOR ||
            c.source_a == SACC && c.format_a != VCT_SCALAR_ACC ||
            c.source_b == SACC && c.format_b != VCT_SCALAR_ACC ||
            c.source_c == SACC && c.format_c != VCT_SCALAR_ACC) return 1'b0;

        if (c.accumulate && (c.fu != VCT_DOT && c.fu != VCT_REDUCTION ||
            c.result_format != VCT_SCALAR_ACC || c.format_c != VCT_SCALAR_ACC)) return 1'b0;

        if (c.write_vacc && c.result_format != VCT_ACC_VECTOR ||
            c.write_sacc && (!(ENABLE_REDUCTION || ENABLE_DOT_PRODUCT) ||
                c.result_format != VCT_SCALAR_ACC)) return 1'b0;

        if (c.write_rf && (c.result_format > VCT_ACC_VECTOR ||
            int'(c.write_slice) + slices > SP)) return 1'b0;

        if (c.write_rf && c.slice_mask != 0) begin
            for (int s = 0; s < SM; s++) begin
                if (selected_slices[s] && (s % SP < c.write_slice ||
                    s % SP >= int'(c.write_slice) + slices)) return 1'b0;
            end
        end

        if (c.source_a == RF0 && (c.format_a > VCT_ACC_VECTOR ||
            int'(c.read_slice_a) + lane_width(c.format_a) / WRITE_SLICE_WIDTH > SP))
            return 1'b0;

        if (c.source_b == RF1 && (c.format_b > VCT_ACC_VECTOR ||
            int'(c.read_slice_b) + lane_width(c.format_b) / WRITE_SLICE_WIDTH > SP))
            return 1'b0;

        for (int p = 0; p < NI; p++) begin
            if (SYNC_PROFILE != 1 && ds[p*DW+:DW] != 0) return 1'b0;
            if (ds[p*DW+:DW] > RDU_TOTAL_DELAY_ENTRIES / NI +
                int'(p < RDU_TOTAL_DELAY_ENTRIES % NI)) return 1'b0;
        end

        return 1'b1;
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

    tile_shell_state #(.WIDTH($bits(validation_t)), .PROTECTION(CONTROL_PROTECTION)) u_validation (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0 &&!o_body_flush),
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
    assign i_body_validate_error_code = validation.legal ? 0 : VCT_ERR_CONTEXT;

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
        logic [VRF_DEPTH*SM-1:0] rf_valid;
        logic [LN-1:0] mask_value;
        logic [LN-1:0] mask_valid;
        logic [7:0] error;
        logic fatal;
    } control_t;

    control_t control;
    control_t control_next;
    wire control_bad;
    wire control_corrected;
    logic [NI-1:0] required_inputs;
    wire integrity_bad;
    wire reset_known = i_rstb === 1'b0 || i_rstb === 1'b1;
    wire private_reset = i_rstb !== 1'b0 && i_execution_state != 0;
    wire clear_private = !private_reset || (o_body_flush &&!i_isolate) ||
        i_power_state == tile_shell_pkg::POWER_OFF;
    wire context_change = o_body_context_active &&!control_bad &&
        i_power_state != tile_shell_pkg::POWER_OFF && (!control.seen ||
        control.context_id != o_body_context_id || control.version != o_body_context_version);
    wire transport_reset = private_reset &&!o_body_flush &&!context_change;
    wire retiring = i_execution_state >= 3 && i_execution_state <= 10;
    wire running = (i_execution_state >= 3 && i_execution_state <= 7 ||
        (i_execution_state == 8 || i_execution_state == 10) && (|required_inputs)) &&
        control.started &&!control.completed &&!control.advance && o_body_context_active &&
        !context_change &&!i_isolate && reset_known &&!o_body_flush &&
        control.error == 0 &&!integrity_bad;
    wire active_context_legal = legal_context(o_body_context_image);
    wire issue;
    wire commit;
    wire advance;
    wire [31:0] queue_count;
    wire pipeline_empty;
    wire synchronized_empty;
    wire transport_empty = pipeline_empty && queue_count == 0 && synchronized_empty;
    wire [NI*DW-1:0] delays = ctx.delays;
    wire use_a = !(ctx.fu == VCT_LANE && ctx.opcode == 17) &&
        !(ctx.fu == VCT_LANE && ctx.opcode == 15 && (ctx.select_mask & ctx.lane_mask) == 0);
    wire use_b = ctx.fu == VCT_DOT || ctx.fu == VCT_LANE &&
        ctx.opcode != 5 && ctx.opcode != 16 &&
        (ctx.opcode != 15 || (ctx.lane_mask & ~ctx.select_mask) != 0);
    wire use_c = ctx.fu == VCT_LANE && ctx.opcode == 21 || ctx.accumulate;
    always @* begin
        required_inputs = '0;

        if (use_a && ctx.source_a < NI) required_inputs[ctx.source_a] = 1'b1;

        if (use_b && ctx.source_b < NI) required_inputs[ctx.source_b] = 1'b1;

        if (use_c && ctx.source_c < NI) required_inputs[ctx.source_c] = 1'b1;
    end

    // Whole vector payloads and metadata share each synchronization entry.
    wire [NI-1:0] synchronized_valid;
    wire [NI*(D+M)-1:0] synchronized_data;
    wire [NI-1:0] synchronized_ready;
    wire [NI-1:0] synchronizer_bad;
    wire [NI-1:0] synchronizer_corrected;

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
        wire [NI*(D+M)-1:0] delayed_data;
        wire [NI-1:0] delayed_valid;
        wire [NI-1:0] delayed_empty;
        wire [NI-1:0] output_empty;
        wire [NI-1:0] output_ready;
        wire [NI-1:0] errors;
        wire rdu_advance = advance;

        for (genvar p = 0; p < NI; p++) begin : g_input
            wire [31:0] occupancy;
            wire bad;
            assign input_data[p*(D+M)+:(D+M)] =
                {o_body_data_in_metadata[p*M+:M], o_body_data_in_payload[p*D+:D]};
            assign i_body_data_in_ready[p] = running && required_inputs[p] &&
                output_ready[p] && rdu_advance;

            // A holding slot per delayed channel prevents skewed source arrival
            // from discarding a complete vector while another channel is missing.
            tile_shell_queue #(
                .WIDTH(D + M),
                .DEPTH(1),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_output (
                .i_clk(i_clk),
                .i_rstb(transport_reset),
                .i_flush(o_body_flush),
                .i_admit(running),
                .i_valid(delayed_valid[p] && rdu_advance),
                .o_ready(output_ready[p]),
                .i_data(delayed_data[p*(D+M)+:(D+M)]),
                .i_deliver(1'b1),
                .o_valid(synchronized_valid[p]),
                .i_ready(synchronized_ready[p]),
                .o_data(synchronized_data[p*(D+M)+:(D+M)]),
                .o_count(occupancy),
                .o_bad(bad),
                .o_corrected(synchronizer_corrected[p])
            );

            assign output_empty[p] = occupancy == 0;
            assign synchronizer_bad[p] = errors[p] || bad;
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
            .i_advance(rdu_advance),
            .i_channel_enable(required_inputs & output_ready),
            .i_delay(delays),
            .i_input_data(input_data),
            .i_input_valid(o_body_data_in_valid & required_inputs & {NI{running}}),
            .i_flush({NI{o_body_flush}}),
            .o_output_data(delayed_data),
            .o_output_valid(delayed_valid),
            .o_output_transfer(),
            .o_channel_empty(delayed_empty),
            .o_all_empty(),
            .o_config_error(errors)
        );

        assign synchronized_empty = (&delayed_empty) && (&output_empty);
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

    logic [M-1:0] input_metadata;
    always @* begin
        input_metadata = '0;

        for (int p = NI - 1; p >= 0; p--)
            if (required_inputs[p]) input_metadata = synchronized_data[p*(D+M)+D+:M];
    end

    wire [LN-1:0] input_mask = input_metadata[MB+3+:LN];
    wire [LN-1:0] tail_mask = input_metadata[MB+4+LN+:LN];
    wire [LN-1:0] base_candidate = ctx.lane_mask &
        (ctx.metadata_mask && (|required_inputs) ? input_mask : {LN{1'b1}}) &
        (ctx.tail_mask ? ctx.runtime_tail &
        ((|required_inputs) ? tail_mask : {LN{1'b1}}) : {LN{1'b1}});
    wire [LN-1:0] candidate_mask = base_candidate &
        (ctx.local_mask ? control.mask_value : {LN{1'b1}});
    wire mask_ready = !ctx.local_mask ||
        (control.mask_valid & base_candidate) === base_candidate;
    wire [LN-1:0] predicate_data[PREDICATE_DEPTH];
    wire [LN-1:0] predicate_valid[PREDICATE_DEPTH];
    wire [LN-1:0] predicate_bad[PREDICATE_DEPTH];
    wire [LN-1:0] predicate_corrected[PREDICATE_DEPTH];
    wire [LN-1:0] predicate_value = (ctx.predicate_mode == VCT_PRED_ALWAYS ? {LN{1'b1}} :
        ctx.predicate_mode == VCT_PRED_EXTERNAL ? o_body_predicate_in_payload :
        ctx.predicate_mode == VCT_PRED_LOCAL ? predicate_data[ctx.predicate_read] :
        {LN{1'b0}}) ^ {LN{ctx.predicate_invert}};
    wire predicate_ready = mask_ready && (ctx.predicate_mode == VCT_PRED_EXTERNAL ?
        o_body_predicate_in_valid[0] === 1'b1 &&
        (^(predicate_value & candidate_mask) !== 1'bx) :
        ctx.predicate_mode != VCT_PRED_LOCAL ||
        ((predicate_valid[ctx.predicate_read] & candidate_mask) === candidate_mask));
    wire [LN-1:0] effective_mask;
    wire [LN-1:0] selected_a_mask = effective_mask &
        (ctx.fu == VCT_LANE && ctx.opcode == 15 ? ctx.select_mask : {LN{1'b1}});
    wire [LN-1:0] selected_b_mask = effective_mask &
        (ctx.fu == VCT_LANE && ctx.opcode == 15 ? ~ctx.select_mask : {LN{1'b1}});

    lane_mask #(.LANES(LN)) u_mask (
        .i_operation_valid(1'b1),
        .i_lane_valid({LN{1'b1}}),
        .i_lane_mask(candidate_mask),
        .i_lane_predicate(predicate_value),
        .o_lane_active(effective_mask),
        .o_lane_isolate(),
        .o_lane_write_mask()
    );

    // A result retains its exact context and all destination addresses until commit.
    typedef struct packed {
        logic [D-1:0] data;
        logic [M-1:0] metadata;
        logic [LN-1:0] lane_mask;
        logic [LN-1:0] predicate;
        logic [LN-1:0] overflow;
        logic [LN-1:0] saturated;
        context_t context_fields;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [OWNER_ID_WIDTH-1:0] owner;
        logic [KERNEL_ID_WIDTH-1:0] kernel;
        logic [31:0] sequence_id;
    } result_t;

    result_t result;
    result_t head;
    wire [D-1:0] commit_data = head.data;
    wire [LN-1:0] commit_mask = head.lane_mask;
    wire commit_local = commit && (|commit_mask);
    context_t destination;
    assign destination = head.context_fields;
    wire commit_rf_enable = commit_local && destination.write_rf;
    wire [SM-1:0] destination_slices = destination.slice_mask;
    wire [VRF_DEPTH*SM-1:0] rf_valid = control.rf_valid;
    logic [VRF_DEPTH*SM-1:0] next_rf_valid;
    logic [SM-1:0] write_mask;
    logic [D-1:0] write_data;

    always @* begin
        write_mask = '0;
        write_data = '0;

        for (int l = 0; l < LN; l++) begin
            for (int s = 0; s < SP; s++) begin
                if (s >= destination.write_slice &&
                    s < int'(destination.write_slice) +
                    lane_width(destination.result_format) / WRITE_SLICE_WIDTH) begin
                    write_mask[l*SP+s] = commit_mask[l] &&
                        (destination.slice_mask == 0 || destination_slices[l*SP+s]);
                    write_data[l*A+s*WRITE_SLICE_WIDTH+:WRITE_SLICE_WIDTH] =
                        commit_data[l*lane_width(destination.result_format) +
                        (s-int'(destination.write_slice))*WRITE_SLICE_WIDTH+:WRITE_SLICE_WIDTH];
                end
            end
        end
    end

    wire [2*D-1:0] rf_reads;
    logic [2*SM-1:0] rf_read_mask;
    wire [1:0] rf_bad;
    wire [1:0] rf_corrected;
    logic rf_available;

    always @* begin
        rf_read_mask = '0;
        rf_available = 1'b1;

        for (int r = 0; r < 2; r++) begin
            for (int l = 0; l < LN; l++) begin
                for (int s = 0; s < SP; s++) begin
                    if (o_body_context_active &&
                        (r == 0 ? selected_a_mask[l] : selected_b_mask[l]) &&
                        (r == 0 ? use_a && ctx.source_a == RF0 :
                        use_b && ctx.source_b == RF1) &&
                        s >= (r == 0 ? ctx.read_slice_a : ctx.read_slice_b) &&
                        s < int'(r == 0 ? ctx.read_slice_a : ctx.read_slice_b) +
                        lane_width(r == 0 ? ctx.format_a : ctx.format_b) / WRITE_SLICE_WIDTH) begin

                        if (rf_valid[int'(r == 0 ? ctx.rf_read_a : ctx.rf_read_b)*SM+
                            l*SP+s] === 1'b1) rf_read_mask[r*SM+l*SP+s] = 1'b1;
                        else rf_available = 1'b0;
                    end
                end
            end
        end

        if ((control.rf_valid & ctx.required_rf) !== ctx.required_rf) rf_available = 1'b0;
    end

    vct_vrf #(
        .LANES(LN),
        .WIDTH(A),
        .SLICE(WRITE_SLICE_WIDTH),
        .DEPTH(VRF_DEPTH),
        .READ_PORTS(VRF_READ_PORTS),
        .WRITE_PORTS(VRF_WRITE_PORTS),
        .PROTECTION(VRF_PROTECTION)
    ) u_vrf (
        .i_clk(i_clk),
        .i_read_mask(rf_read_mask),
        .i_read_address({ctx.rf_read_b, ctx.rf_read_a}),
        .o_read_data(rf_reads),
        .o_bad(rf_bad),
        .o_corrected(rf_corrected),
        .i_write(commit_rf_enable),
        .i_write_mask(write_mask),
        .i_write_address(destination.rf_write),
        .i_write_data(write_data)
    );

    wire [LN-1:0] vacc_valid[VECTOR_ACC_DEPTH];
    wire [D-1:0] vacc_data[VECTOR_ACC_DEPTH];
    wire [LN-1:0] vacc_signed[VECTOR_ACC_DEPTH];
    wire [LN-1:0] vacc_saturate[VECTOR_ACC_DEPTH];
    wire [LN-1:0] vacc_bad[VECTOR_ACC_DEPTH];
    wire [LN-1:0] vacc_corrected[VECTOR_ACC_DEPTH];
    wire [SCALAR_ACC_DEPTH-1:0] sacc_valid;
    wire [SCALAR_ACC_DEPTH*A-1:0] sacc_data;
    wire [SCALAR_ACC_DEPTH-1:0] sacc_signed;
    wire [SCALAR_ACC_DEPTH-1:0] sacc_saturate;
    wire [SCALAR_ACC_DEPTH-1:0] sacc_bad;
    wire [SCALAR_ACC_DEPTH-1:0] sacc_corrected;

    for (genvar vacc_index = 0; vacc_index < VECTOR_ACC_DEPTH; vacc_index++) begin : g_vacc
        vct_accumulator #(
            .LANES(LN),
            .WIDTH(A),
            .PROTECTION(VRF_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_entry (
            .i_clk(i_clk),
            .i_rstb(!clear_private),
            .i_invalidate(context_change ? ctx.invalidate_vacc[vacc_index*LN+:LN] : {LN{1'b0}}),
            .i_clear(context_change ? ctx.clear_vacc[vacc_index*LN+:LN] : {LN{1'b0}}),
            .i_write({LN{commit_local && destination.write_vacc &&
                destination.vacc_write == vacc_index}} & commit_mask),
            .i_data(head.data),
            .i_signed(ctx.signed_mode),
            .i_saturate(ctx.saturate),
            .o_data(vacc_data[vacc_index]),
            .o_valid(vacc_valid[vacc_index]),
            .o_signed(vacc_signed[vacc_index]),
            .o_saturate(vacc_saturate[vacc_index]),
            .o_bad(vacc_bad[vacc_index]),
            .o_corrected(vacc_corrected[vacc_index])
        );
    end

    if (ENABLE_REDUCTION || ENABLE_DOT_PRODUCT) begin : g_sacc
        for (genvar sacc_index = 0; sacc_index < SCALAR_ACC_DEPTH; sacc_index++) begin : g_entry
            vct_accumulator #(
                .LANES(1),
                .WIDTH(A),
                .PROTECTION(VRF_PROTECTION),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_value (
                .i_clk(i_clk),
                .i_rstb(!clear_private),
                .i_invalidate(context_change && ctx.invalidate_sacc[sacc_index]),
                .i_clear(context_change && ctx.clear_sacc[sacc_index]),
                .i_write(commit_local && destination.write_sacc &&
                    destination.sacc_write == sacc_index),
                .i_data(commit_data[A-1:0]),
                .i_signed(ctx.signed_mode),
                .i_saturate(ctx.saturate),
                .o_data(sacc_data[sacc_index*A+:A]),
                .o_valid(sacc_valid[sacc_index]),
                .o_signed(sacc_signed[sacc_index]),
                .o_saturate(sacc_saturate[sacc_index]),
                .o_bad(sacc_bad[sacc_index]),
                .o_corrected(sacc_corrected[sacc_index])
            );
        end
    end else begin : g_no_sacc
        assign sacc_valid = '0;
        assign sacc_data = '0;
        assign sacc_signed = '0;
        assign sacc_saturate = '0;
        assign sacc_bad = '0;
        assign sacc_corrected = '0;
    end

    for (genvar p = 0; p < PREDICATE_DEPTH; p++) begin : g_predicate
        wire [LN-1:0] raw_data;
        wire [LN-1:0] raw_valid;
        wire write_entry = commit_local && destination.write_predicate &&
            destination.predicate_write == p;
        wire [LN-1:0] invalidate = context_change ?
            ctx.invalidate_predicate[p*LN+:LN] : {LN{1'b0}};

        predicate_unit #(.PRED_DEPTH(1), .NUM_LANES(LN), .ASYNC_RESET(ASYNC_RESET)) u_value (
            .i_clk(i_clk),
            .i_rstb(!clear_private),
            .i_clock_enable(1'b1),
            .i_valid(1'b1),
            .i_opcode((|invalidate) ? predicate_unit_pkg::PRED_INVALIDATE :
                write_entry ? predicate_unit_pkg::PRED_LOAD : predicate_unit_pkg::PRED_PASS_A),
            .i_lane_mask((|invalidate) ? invalidate : write_entry ? commit_mask : {LN{1'b1}}),
            .i_source_a_addr(1'b0),
            .i_source_b_addr(1'b0),
            .i_destination_addr(1'b0),
            .i_predicate_input(head.predicate),
            .i_write_enable(write_entry || (|invalidate)),
            .o_result(raw_data),
            .o_result_valid(raw_valid),
            .o_valid(),
            .o_any(),
            .o_all(),
            .o_updated_mask(),
            .o_invalidated(),
            .o_illegal_operation()
        );

        for (genvar l = 0; l < LN; l++) begin : g_lane
            wire [1:0] witness;
            wire bad;

            tile_shell_state #(.WIDTH(2), .PROTECTION(CONTROL_PROTECTION)) u_witness (
                .i_clk(i_clk),
                .i_rstb(!clear_private &&!invalidate[l]),
                .i_enable(write_entry && commit_mask[l]),
                .i_data({1'b1, head.predicate[l]}),
                .o_data(witness),
                .o_bad(bad),
                .o_corrected(predicate_corrected[p][l])
            );

            assign predicate_data[p][l] = witness[0];
            assign predicate_valid[p][l] = witness[1];
            assign predicate_bad[p][l] = bad || raw_valid[l] !== witness[1] ||
                (witness[1] && raw_data[l] !== witness[0]);
        end
    end

    localparam int BW = D + 3 + LN;
    wire [BW:0] bypass_state;
    wire [BW:0] previous_state;
    wire bypass_bad;
    wire previous_bad;
    wire bypass_corrected;
    wire previous_corrected;
    logic [BW-1:0] bypass_record;
    logic [D-1:0] bypass_payload;
    logic [LN-1:0] bypass_mask;

    always @* begin
        bypass_payload = head.data;
        bypass_mask = commit_mask;

        if (bypass_state[BW] && destination.result_format < 3 &&
            bypass_state[D+:3] == destination.result_format) begin
            bypass_mask = bypass_state[D+3+:LN] | commit_mask;

            for (int bit_index = 0; bit_index < D; bit_index++) begin
                if (bit_index < format_width(destination.result_format) &&
                    !commit_mask[bit_index / lane_width(destination.result_format)])
                    bypass_payload[bit_index] = bypass_state[bit_index];
            end
        end

        bypass_record = {bypass_mask, destination.result_format, bypass_payload};
    end

    wire [BW-1:0] previous_record = {commit_mask, destination.result_format, head.data};

    tile_shell_state #(.WIDTH(BW + 1), .PROTECTION(CONTROL_PROTECTION)) u_bypass (
        .i_clk(i_clk),
        .i_rstb(!clear_private &&!(context_change && ctx.invalidate_bypass)),
        .i_enable(commit_local && destination.write_bypass),
        .i_data({1'b1, bypass_record}),
        .o_data(bypass_state),
        .o_bad(bypass_bad),
        .o_corrected(bypass_corrected)
    );

    tile_shell_state #(.WIDTH(BW + 1), .PROTECTION(CONTROL_PROTECTION)) u_previous (
        .i_clk(i_clk),
        .i_rstb(!clear_private &&!(context_change && ctx.invalidate_bypass)),
        .i_enable(commit_local),
        .i_data({1'b1, previous_record}),
        .o_data(previous_state),
        .o_bad(previous_bad),
        .o_corrected(previous_corrected)
    );

    logic [NS*D-1:0] source_data;
    logic [NS-1:0] source_valid;

    always @* begin
        source_data = '0;
        source_valid = '0;

        for (int p = 0; p < NI; p++) begin
            source_data[p*D+:D] = synchronized_data[p*(D+M)+:D];
            source_valid[p] = synchronized_valid[p];
        end

        for (int l = 0; l < LN; l++) begin
            source_data[RF0*D+l*lane_width(ctx.format_a)+:A] =
                A'(rf_reads[l*A+:A] >> (ctx.read_slice_a * WRITE_SLICE_WIDTH));
            source_data[RF1*D+l*lane_width(ctx.format_b)+:A] =
                A'(rf_reads[D+l*A+:A] >> (ctx.read_slice_b * WRITE_SLICE_WIDTH));
        end

        source_valid[RF0] = rf_available;
        source_valid[RF1] = rf_available;
        source_data[IMM*D+:D] = ctx.immediate;
        source_valid[IMM] = 1'b1;
        source_valid[ZERO] = 1'b1;
        source_data[VACC*D+:D] = vacc_data[ctx.vacc_write];
        source_valid[VACC] = (vacc_valid[ctx.vacc_write] & effective_mask) === effective_mask &&
            ((vacc_signed[ctx.vacc_write] ^ {LN{ctx.signed_mode}}) & effective_mask) == 0 &&
            ((vacc_saturate[ctx.vacc_write] ^ {LN{ctx.saturate}}) & effective_mask) == 0;
        source_data[SACC*D+:A] = sacc_data[ctx.sacc_write*A+:A];
        source_valid[SACC] = sacc_valid[ctx.sacc_write] &&
            sacc_signed[ctx.sacc_write] == ctx.signed_mode &&
            sacc_saturate[ctx.sacc_write] == ctx.saturate;
        source_data[BYPASS*D+:D] = bypass_state[D-1:0];
        source_valid[BYPASS] = bypass_state[BW] &&
            (bypass_state[D+3+:LN] & effective_mask) == effective_mask;
        source_data[PREVIOUS*D+:D] = previous_state[D-1:0];
        source_valid[PREVIOUS] = previous_state[BW] &&
            (previous_state[D+3+:LN] & effective_mask) == effective_mask;
    end

    wire [3*D-1:0] operands;
    wire [2:0] operands_valid;
    wire [2:0] selection_error;

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
        .i_destination_enable({use_c, use_b, use_a}),
        .i_select({ctx.source_c, ctx.source_b, ctx.source_a}),
        .i_capture_enable(3'b0),
        .i_flush(o_body_flush),
        .o_destination_data(operands),
        .o_destination_valid(operands_valid),
        .o_selection_error(selection_error)
    );

    wire [D-1:0] a = operands[0+:D];
    wire [D-1:0] b = operands[D+:D];
    wire [D-1:0] c = operands[2*D+:D];
    logic live_ready;
    wire [PREDICATE_DEPTH*LN-1:0] required_predicate = ctx.required_predicate;
    wire [VECTOR_ACC_DEPTH*LN-1:0] required_vacc = ctx.required_vacc;

    always @* begin
        live_ready = (control.mask_valid & ctx.required_mask) === ctx.required_mask &&
            (sacc_valid & ctx.required_sacc) === ctx.required_sacc;

        for (int p = 0; p < PREDICATE_DEPTH; p++)
            if ((predicate_valid[p] & required_predicate[p*LN+:LN]) !==
                required_predicate[p*LN+:LN]) live_ready = 1'b0;

        for (int a = 0; a < VECTOR_ACC_DEPTH; a++)
            if ((vacc_valid[a] & required_vacc[a*LN+:LN]) !== required_vacc[a*LN+:LN])
                live_ready = 1'b0;
    end

    wire sources_ready = (!(|required_inputs) || joined_valid) && predicate_ready && live_ready &&
        (!use_a || operands_valid[0]) && (!use_b || operands_valid[1]) &&
        (!use_c || operands_valid[2]);
    logic canonical;
    logic [2:0] checked_format;
    logic [SW-1:0] checked_source;
    logic [D-1:0] checked_operand;
    logic [LN-1:0] checked_lanes;

    always @* begin
        canonical = (^effective_mask !== 1'bx);
        checked_format = '0;
        checked_source = '0;
        checked_operand = '0;
        checked_lanes = '0;

        for (int o = 0; o < 3; o++) begin
            if (o == 0 && use_a || o == 1 && use_b || o == 2 && use_c) begin
                checked_format = o == 0 ? ctx.format_a : o == 1 ? ctx.format_b : ctx.format_c;
                checked_source = o == 0 ? ctx.source_a : o == 1 ? ctx.source_b : ctx.source_c;
                checked_operand = operands[o*D+:D];
                checked_lanes = o == 0 ? selected_a_mask :
                    o == 1 ? selected_b_mask : effective_mask;

                for (int bit_index = 0; bit_index < D; bit_index++) begin
                    if (bit_index >= format_width(checked_format)) begin
                        if (REQUIRE_CANONICAL_FORMAT == 1 &&
                            checked_operand[bit_index] !== 1'b0) canonical = 1'b0;
                    end else if (checked_format >= 3 ? (|checked_lanes) :
                        checked_lanes[bit_index / lane_width(checked_format)]) begin

                        if (checked_operand[bit_index] !== 1'b0 &&
                            checked_operand[bit_index] !== 1'b1) canonical = 1'b0;
                    end
                end

                if (checked_source < NI) begin
                    if (synchronized_data[int'(checked_source)*(D+M)+D+MB+:3] !==
                        checked_format || synchronized_data[int'(checked_source)*(D+M)+D+
                        MB+3+LN] !== ctx.signed_mode) canonical = 1'b0;
                end

                if (checked_source == BYPASS && bypass_state[D+:3] !== checked_format)
                    canonical = 1'b0;

                if (checked_source == PREVIOUS && previous_state[D+:3] !== checked_format)
                    canonical = 1'b0;
            end
        end

        for (int p = 0; p < NI; p++) begin
            if (required_inputs[p] && synchronized_valid[p] &&
                (synchronized_data[p*(D+M)+D+MB+3+:LN] !== input_mask ||
                synchronized_data[p*(D+M)+D+MB+4+LN+:LN] !== tail_mask)) canonical = 1'b0;
        end
    end

    // Arithmetic dependencies are combinational here. Protected delay stages below
    // implement the generated enabled-cycle latency and hold complete result records.
    wire fu_enable = running && sources_ready && canonical && pipeline_empty && queue_count == 0;
    wire [D-1:0] lane_results;
    wire [LN-1:0] lane_predicates;
    wire [LN-1:0] lane_overflow;
    wire [LN-1:0] lane_saturated;
    wire [LN-1:0] lane_illegal;

    for (genvar l = 0; l < LN; l++) begin : g_lane
        vector_lane #(
            .ELEMENT_WIDTH(EL),
            .ACC_WIDTH(A),
            .ENABLE_ALU(ENABLE_LANE_ALU),
            .SUPPORT_MUL(SUPPORT_MUL),
            .SUPPORT_MAC(SUPPORT_MAC),
            .SUPPORT_SATURATION(SUPPORT_SATURATION),
            .SUPPORT_MINMAX(SUPPORT_MINMAX),
            .LANE_LATENCY(0),
            .MUL_LATENCY(0),
            .MAC_LATENCY(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_lane (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(1'b1),
            .i_valid(fu_enable && ctx.fu == VCT_LANE),
            .i_lane_enable(effective_mask[l]),
            .i_predicate_enable(1'b0),
            .i_execute_predicate(1'b1),
            .i_select_predicate(ctx.select_mask[l]),
            .i_opcode(ctx.opcode),
            .i_operand_a(a[l*EL+:EL]),
            .i_operand_b(b[l*EL+:EL]),
            .i_accumulator(c[l*A+:A]),
            .i_signed(ctx.signed_mode),
            .i_saturate(ctx.saturate),
            .o_result(lane_results[l*A+:A]),
            .o_predicate(lane_predicates[l]),
            .o_overflow(lane_overflow[l]),
            .o_saturated(lane_saturated[l]),
            .o_illegal_operation(lane_illegal[l]),
            .o_valid(),
            .o_write_enable(),
            .o_suppressed(),
            .o_result_format(),
            .o_result_signed(),
            .o_predicate_valid(),
            .o_carry(),
            .o_borrow(),
            .o_zero(),
            .o_negative()
        );
    end

    wire [LN*EL-1:0] compact_elements;
    wire [LN*2*EL-1:0] compact_products;

    for (genvar f = 0; f < 2; f++) begin : g_pack
        localparam int WIDTH = f == 0 ? EL : 2 * EL;
        wire [LN*WIDTH-1:0] packed_data;

        packer #(
            .NUM_ELEMENTS(LN),
            .SRC_ELEMENT_WIDTH(A),
            .DST_ELEMENT_WIDTH(WIDTH),
            .SUPPORT_REVERSE(0),
            .SUPPORT_SATURATION(0)
        ) u_packer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(o_body_flush),
            .i_valid(fu_enable && ctx.fu == VCT_LANE),
            .o_ready(),
            .i_data(lane_results),
            .i_lane_valid(effective_mask),
            .i_signed(1'b0),
            .i_saturate(1'b0),
            .i_reverse(1'b0),
            .i_last(1'b1),
            .i_user(1'b0),
            .o_valid(),
            .i_ready(1'b1),
            .o_data(packed_data),
            .o_lane_valid(),
            .o_overflow(),
            .o_saturated(),
            .o_any_overflow(),
            .o_any_saturated(),
            .o_last(),
            .o_user(),
            .o_config_error(),
            .o_busy()
        );

        if (f == 0) assign compact_elements = packed_data;
        else assign compact_products = packed_data;
    end

    wire [A-1:0] reduction_result;
    wire reduction_illegal;
    wire [A-1:0] accumulated_reduction;
    wire reduction_overflow;
    wire reduction_saturated;

    if (ENABLE_REDUCTION) begin : g_reduction
        wire [A-1:0] raw;
        vector_reduction #(
            .ELEMENT_WIDTH(EL),
            .NUM_ELEMENTS(LN),
            .ACC_WIDTH(A),
            .LATENCY(0),
            .SUPPORT_MINMAX(SUPPORT_MINMAX)
        ) u_reduction (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(1'b1),
            .i_valid(fu_enable && ctx.fu == VCT_REDUCTION),
            .i_opcode(ctx.opcode[2:0]),
            .i_element_mask(effective_mask),
            .i_data(a[LN*EL-1:0]),
            .i_signed(ctx.signed_mode),
            .o_result(raw),
            .o_illegal_operation(reduction_illegal),
            .o_valid(),
            .o_result_format(),
            .o_result_signed(),
            .o_active_count(),
            .o_zero(),
            .o_negative()
        );

        scalar_alu #(.DATA_WIDTH(A), .SUPPORT_SATURATION(SUPPORT_SATURATION)) u_accumulate (
            .i_enable(fu_enable && ctx.fu == VCT_REDUCTION && ctx.accumulate),
            .i_opcode(scalar_alu_pkg::ALU_ADD),
            .i_operand_a(raw),
            .i_operand_b(c[A-1:0]),
            .i_predicate(1'b1),
            .i_signed(ctx.signed_mode),
            .i_saturate(ctx.saturate),
            .o_result(accumulated_reduction),
            .o_overflow(reduction_overflow),
            .o_saturated(reduction_saturated),
            .o_carry(),
            .o_borrow(),
            .o_predicate(),
            .o_zero(),
            .o_negative(),
            .o_illegal_operation()
        );

        assign reduction_result = ctx.accumulate ? accumulated_reduction : raw;
    end else begin : g_no_reduction
        assign reduction_result = '0;
        assign accumulated_reduction = '0;
        assign reduction_illegal = 1'b0;
        assign reduction_overflow = 1'b0;
        assign reduction_saturated = 1'b0;
    end

    wire [A-1:0] dot_result;
    wire dot_illegal;
    wire dot_overflow;
    wire dot_saturated;

    if (ENABLE_DOT_PRODUCT) begin : g_dot
        dot_product #(
            .ELEMENT_WIDTH(EL),
            .NUM_TERMS(LN),
            .ACC_WIDTH(A),
            .LATENCY(0),
            .SUPPORT_SATURATION(SUPPORT_SATURATION)
        ) u_dot (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(1'b1),
            .i_valid(fu_enable && ctx.fu == VCT_DOT),
            .i_term_mask(effective_mask),
            .i_operand_a(a[LN*EL-1:0]),
            .i_operand_b(b[LN*EL-1:0]),
            .i_accumulate(ctx.accumulate),
            .i_accumulator(c[A-1:0]),
            .i_signed(ctx.signed_mode), .i_saturate(ctx.saturate),
            .o_result(dot_result), .o_illegal_operation(dot_illegal),
            .o_overflow(dot_overflow), .o_saturated(dot_saturated), .o_valid(),
            .o_active_count(), .o_carry(), .o_zero(), .o_negative()
        );
    end else begin : g_no_dot
        assign dot_result = '0;
        assign dot_illegal = 1'b0;
        assign dot_overflow = 1'b0;
        assign dot_saturated = 1'b0;
    end

    logic [D-1:0] result_payload;

    always @* begin
        result_payload = '0;
        result = '0;
        result.lane_mask = effective_mask;
        result.context_fields = ctx;
        result.context_id = o_body_context_id;
        result.version = o_body_context_version;
        result.owner = i_owner;
        result.kernel = i_kernel;
        result.sequence_id = control.sequence_id;
        result.metadata = (M'(o_body_context_version) << CI) | M'(o_body_context_id) |
            (M'(ctx.result_format) << MB) | (M'(effective_mask) << (MB + 3)) |
            (M'(ctx.signed_mode) << (MB + 3 + LN));

        case (ctx.fu)
            VCT_LANE: begin
                result_payload = ctx.result_format == VCT_ELEMENT_VECTOR ? D'(compact_elements) :
                    ctx.result_format == VCT_PRODUCT_VECTOR ? D'(compact_products) : lane_results;
                result.predicate = lane_predicates & effective_mask;
                result.overflow = lane_overflow & effective_mask;
                result.saturated = lane_saturated & effective_mask;
            end
            VCT_REDUCTION: begin
                result_payload = ctx.result_format == VCT_SCALAR_ELEMENT ?
                    D'(reduction_result[EL-1:0]) : D'(reduction_result);
                result.overflow = {LN{ctx.accumulate && reduction_overflow}} & effective_mask;
                result.saturated = {LN{ctx.accumulate && reduction_saturated}} & effective_mask;
            end
            VCT_DOT: begin
                result_payload = D'(dot_result);
                result.overflow = {LN{dot_overflow}} & effective_mask;
                result.saturated = {LN{dot_saturated}} & effective_mask;
            end
            VCT_BROADCAST: begin
                for (int l = 0; l < LN; l++) begin
                    if (effective_mask[l]) begin
                        if (ctx.result_format == VCT_ELEMENT_VECTOR)
                            result_payload[l*EL+:EL] = a[EL-1:0];
                        else result_payload[l*A+:A] = a[A-1:0];
                    end
                end
            end
            VCT_EXTRACT: begin
                if (ctx.format_a == VCT_ELEMENT_VECTOR)
                    result_payload = D'(EL'(a >> (ctx.extract_lane * EL)));
                else if (ctx.format_a == VCT_PRODUCT_VECTOR) begin
                    if (ctx.signed_mode)
                        result_payload =
                            D'(A'($signed((2 * EL)'(a >> (ctx.extract_lane * 2 * EL)))));
                    else result_payload = D'((2 * EL)'(a >> (ctx.extract_lane * 2 * EL)));
                end else result_payload = D'(A'(a >> (ctx.extract_lane * A)));
            end
            VCT_PASS: begin
                for (int l = 0; l < LN; l++) begin
                    for (int bit_index = 0; bit_index < A; bit_index++) begin
                        if (ctx.result_format < 3 && effective_mask[l] &&
                            bit_index < lane_width(ctx.result_format))
                            result_payload[l*lane_width(ctx.result_format)+bit_index] =
                                a[l*lane_width(ctx.result_format)+bit_index];
                    end
                end

                if (ctx.result_format >= 3 && (|effective_mask))
                    result_payload = a & ({D{1'b1}} >> (D - format_width(ctx.result_format)));
            end
            default: result_payload = '0;
        endcase

        if (effective_mask == 0) result_payload = '0;

        result.data = result_payload;
    end

    // Conservative serialization removes implicit read-after-write bypass. Every
    // operation reserves its complete result before consuming an input token.
    localparam int MAX0 = LANE_LATENCY > REDUCTION_LATENCY ? LANE_LATENCY : REDUCTION_LATENCY;
    localparam int MAX1 = MAX0 > DOT_LATENCY ? MAX0 : DOT_LATENCY;
    localparam int PIPE = MAX1 + REGISTER_BYPASS > 0 ? MAX1 + REGISTER_BYPASS : 1;
    localparam int RW = $bits(result_t);
    wire [PIPE-1:0] pipeline_valid;
    wire [RW-1:0] pipeline_data[PIPE];
    wire [PIPE-1:0] pipeline_bad;
    wire [PIPE-1:0] pipeline_corrected;
    wire queue_ready;
    wire queue_valid;
    wire queue_bad;
    wire queue_corrected;
    assign pipeline_empty = !(|pipeline_valid);
    wire source_registered = REGISTER_BYPASS == 1 &&
        ((use_a && ctx.source_a == BYPASS) || (use_b && ctx.source_b == BYPASS) ||
        (use_c && ctx.source_c == BYPASS));
    wire [31:0] latency = (ctx.fu == VCT_LANE ? LANE_LATENCY :
        ctx.fu == VCT_REDUCTION ? REDUCTION_LATENCY : ctx.fu == VCT_DOT ? DOT_LATENCY : 0) +
        int'(source_registered);
    assign advance = retiring && i_clock_enable === 1'b1 &&!i_isolate &&!o_body_flush &&
        queue_ready &&!integrity_bad && control.error == 0;
    wire count_available = ctx.iterations == 0 || control.issued < ctx.iterations;
    wire empty_illegal = ctx.fu == VCT_REDUCTION && (ctx.opcode == 1 || ctx.opcode == 2) &&
        effective_mask == 0 || ctx.fu == VCT_EXTRACT &&!effective_mask[ctx.extract_lane];
    wire fu_illegal = ctx.fu == VCT_LANE && (|lane_illegal) ||
        ctx.fu == VCT_REDUCTION && reduction_illegal || ctx.fu == VCT_DOT && dot_illegal;
    wire trap = ctx.trap_overflow && (|result.overflow);
    assign issue = fu_enable && active_context_legal && advance && count_available &&
        !empty_illegal &&!fu_illegal &&!trap;
    assign i_body_predicate_in_ready[0] = issue && ctx.predicate_mode == VCT_PRED_EXTERNAL;
    assign i_body_event_in_ready[0] = running && ctx.advance_mode == VCT_ADVANCE_EVENT &&
        transport_empty;

    for (genvar p = 0; p < PIPE; p++) begin : g_pipeline
        wire incoming_valid;
        wire [RW-1:0] incoming_data;

        if (p < PIPE - 1) begin : g_next
            assign incoming_valid = (issue && latency == p + 1) || pipeline_valid[p+1];
            assign incoming_data = issue && latency == p + 1 ? result : pipeline_data[p+1];
        end else begin : g_last
            assign incoming_valid = issue && latency == p + 1;
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

    tile_shell_queue #(
        .WIDTH(RW),
        .DEPTH(RESULT_QUEUE_DEPTH),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_results (
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

    wire ownership_ok = head.context_id == o_body_context_id &&
        head.version == o_body_context_version && head.owner == i_owner && head.kernel == i_kernel;
    wire [NO-1:0] head_outputs = (|head.lane_mask) || destination.false_token ?
        destination.output_mask : {NO{1'b0}};
    wire head_predicate_output = destination.predicate_output && (|head.lane_mask);
    wire destinations_ready = (o_body_data_out_ready & head_outputs) === head_outputs &&
        (!head_predicate_output || o_body_predicate_out_ready[0] === 1'b1);
    assign commit = queue_valid && active_context_legal && destinations_ready && ownership_ok &&
        retiring && i_clock_enable === 1'b1 &&!i_isolate &&!o_body_flush &&
        !integrity_bad && control.error == 0 && reset_known;

    for (genvar p = 0; p < NO; p++) begin : g_output
        assign i_body_data_out_valid[p] = commit && head_outputs[p];
        assign i_body_data_out_payload[p*D+:D] = i_body_data_out_valid[p] ? head.data : '0;
        assign i_body_data_out_metadata[p*M+:M] = queue_valid ? head.metadata : '0;
    end

    assign i_body_predicate_out_valid[0] = commit && head_predicate_output;
    assign i_body_predicate_out_payload = i_body_predicate_out_valid[0] ? head.predicate : '0;
    assign i_body_predicate_out_metadata = queue_valid ? PM'(head.context_id) : '0;
    assign i_body_event_out_valid = '0;
    assign i_body_event_out_payload = '0;

    logic stored_bad;
    logic stored_corrected;

    always @* begin
        stored_bad = (|sacc_bad);
        stored_corrected = (|sacc_corrected);

        for (int p = 0; p < PREDICATE_DEPTH; p++) begin
            stored_bad = stored_bad || (|predicate_bad[p]);
            stored_corrected = stored_corrected || (|predicate_corrected[p]);
        end

        for (int a = 0; a < VECTOR_ACC_DEPTH; a++) begin
            stored_bad = stored_bad || (|vacc_bad[a]);
            stored_corrected = stored_corrected || (|vacc_corrected[a]);
        end
    end

    assign integrity_bad = control_bad || validation_bad || bypass_bad || previous_bad ||
        stored_bad || (|rf_bad) || (|pipeline_bad) || queue_bad || (|synchronizer_bad);
    wire corrected = control_corrected || validation_corrected || bypass_corrected ||
        previous_corrected || stored_corrected || (|rf_corrected) ||
        (|pipeline_corrected) || queue_corrected || (|synchronizer_corrected);
    wire context_error = running &&!active_context_legal;
    wire format_error = running && pipeline_empty && queue_count == 0 && sources_ready &&!canonical;
    wire missing_source = running && pipeline_empty && queue_count == 0 &&
        (!(|required_inputs) || joined_valid) &&
        (!rf_available ||!predicate_ready ||!live_ready ||
        (use_a && ctx.source_a >= NI &&!operands_valid[0]) ||
        (use_b && ctx.source_b >= NI &&!operands_valid[1]) ||
        (use_c && ctx.source_c >= NI &&!operands_valid[2]));
    wire schedule_error = SYNC_PROFILE != 2 && missing_source;
    wire numerical_error = fu_enable && count_available && (empty_illegal || fu_illegal || trap);

    always @* begin
        control_next = control;
        next_rf_valid = rf_valid;

        if (context_change) begin
            control_next.seen = 1'b1;
            control_next.context_id = o_body_context_id;
            control_next.version = o_body_context_version;
            control_next.started = i_execution_state >= 3 && i_execution_state <= 7;
            control_next.completed = 1'b0;
            control_next.advance = 1'b0;
            control_next.issued = '0;
            control_next.committed = '0;
            next_rf_valid = rf_valid & ~ctx.invalidate_rf;
            control_next.mask_valid = control.mask_valid & ~ctx.invalidate_mask;
        end

        if (o_body_start || o_body_resume) control_next.started = 1'b1;

        if (issue) begin
            control_next.issued = control.issued + 1'b1;
            control_next.sequence_id = control.sequence_id + 1'b1;
        end

        if (commit) begin
            control_next.committed = control.committed + 1'b1;

            if (commit_rf_enable)
                next_rf_valid[destination.rf_write*SM+:SM] =
                    rf_valid[destination.rf_write*SM+:SM] | write_mask;

            if (commit_local && destination.write_mask) begin
                control_next.mask_value = (control.mask_value & ~commit_mask) |
                    (head.predicate & commit_mask);
                control_next.mask_valid = control.mask_valid | commit_mask;
            end

            if (ctx.iterations != 0 && control.committed + 1'b1 == ctx.iterations) begin
                if (ctx.advance_mode == VCT_ADVANCE_COUNT) control_next.advance = 1'b1;
                else if (ctx.terminal) control_next.completed = 1'b1;
            end

            if (ctx.advance_mode == VCT_ADVANCE_PREDICATE && (|head.predicate))
                control_next.advance = 1'b1;
        end

        if (o_body_event_in_valid[0] && i_body_event_in_ready[0]) control_next.advance = 1'b1;

        if (o_advance_valid && i_advance_ready) begin
            control_next.advance = 1'b0;
            control_next.seen = 1'b0;
        end

        if (integrity_bad || queue_valid &&!ownership_ok) begin
            control_next.error = integrity_bad ? VCT_ERR_INTEGRITY : VCT_ERR_OWNERSHIP;
            control_next.fatal = 1'b1;
        end else if (context_error) control_next.error = VCT_ERR_CONTEXT;
        else if (format_error) control_next.error = VCT_ERR_FORMAT;
        else if (schedule_error) control_next.error = VCT_ERR_SOURCE;
        else if (numerical_error) control_next.error = trap ? VCT_ERR_OVERFLOW : VCT_ERR_EMPTY;

        control_next.rf_valid = next_rf_valid;

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

    wire fatal_latched;
    wire fault_bad;

    tile_shell_state #(.WIDTH(1), .PROTECTION(CONTROL_PROTECTION)) u_fault (
        .i_clk(i_clk),
        .i_rstb(!clear_private),
        .i_enable(reset_known && (integrity_bad || queue_valid &&!ownership_ok)),
        .i_data(1'b1),
        .o_data(fatal_latched),
        .o_bad(fault_bad),
        .o_corrected()
    );

    assign o_advance_valid = control.advance && transport_empty &&!control.fatal;
    assign o_advance_context = ctx.next_context;
    assign i_body_completed = control.completed && transport_empty &&!control.fatal;
    assign i_body_safe_point = transport_empty &&!context_change &&!issue &&!commit;
    assign i_body_drain_done = transport_empty;
    assign i_body_idle = transport_empty;
    assign i_body_busy = !transport_empty;
    assign i_body_stall_reasons = {4'b0, running &&!sources_ready, 1'b0,
        queue_valid &&!destinations_ready, running && (!sources_ready ||!rf_available)};
    assign i_body_error = corrected || control.error != 0 || context_error ||
        format_error || schedule_error || numerical_error;
    assign i_body_fatal_error = control.fatal || fatal_latched || fault_bad;
    assign i_body_error_code = corrected ? VCT_ERR_CORRECTED : integrity_bad ? VCT_ERR_INTEGRITY :
        context_error ? VCT_ERR_CONTEXT : format_error ? VCT_ERR_FORMAT :
        schedule_error ? VCT_ERR_SOURCE : numerical_error ?
        (trap ? VCT_ERR_OVERFLOW : VCT_ERR_EMPTY) : control.error;
    assign i_body_wakeup_required = !transport_empty || (o_body_context_active &&
        (o_body_validate_valid || (|o_body_data_in_valid) || (|o_body_predicate_in_valid)));

    // Weighted event increments distinguish vector issues from useful lane work.
    localparam int INCREMENT = $clog2(2 * SM + 1) > 8 ? $clog2(2 * SM + 1) : 8;
    logic [32*INCREMENT-1:0] event_increment;
    logic [32*5-1:0] event_select;

    always @* begin
        event_increment = '0;
        event_select = '0;

        for (int e = 0; e < 32; e++) event_select[e*5+:5] = 5'(e);

        event_increment[0*INCREMENT+:INCREMENT] = INCREMENT'(issue);
        event_increment[1*INCREMENT+:INCREMENT] = INCREMENT'(commit);
        event_increment[2*INCREMENT+:INCREMENT] =
            issue ? INCREMENT'($countones(effective_mask)) : 0;
        event_increment[3*INCREMENT+:INCREMENT] =
            issue ? INCREMENT'(LN - $countones(effective_mask)) : 0;
        event_increment[4*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.fu == VCT_LANE);
        event_increment[5*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.opcode == 20);
        event_increment[6*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.opcode == 21);
        event_increment[7*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.fu == VCT_REDUCTION);
        event_increment[8*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.fu == VCT_DOT);
        event_increment[9*INCREMENT+:INCREMENT] = issue ? INCREMENT'($countones(rf_read_mask)) : 0;
        event_increment[10*INCREMENT+:INCREMENT] =
            commit_rf_enable ? INCREMENT'($countones(write_mask)) : 0;
        event_increment[11*INCREMENT+:INCREMENT] = INCREMENT'(missing_source);
        event_increment[12*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.predicate_mode != 0);
        event_increment[13*INCREMENT+:INCREMENT] =
            INCREMENT'(commit_local && destination.write_predicate);
        event_increment[14*INCREMENT+:INCREMENT] = INCREMENT'(issue && effective_mask == 0);
        event_increment[15*INCREMENT+:INCREMENT] =
            INCREMENT'(commit_local && destination.write_vacc);
        event_increment[16*INCREMENT+:INCREMENT] =
            INCREMENT'(commit_local && destination.write_sacc);
        event_increment[17*INCREMENT+:INCREMENT] =
            INCREMENT'(commit_local && destination.write_bypass);
        event_increment[18*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.fu == VCT_BROADCAST);
        event_increment[19*INCREMENT+:INCREMENT] = INCREMENT'(issue && ctx.fu == VCT_EXTRACT);
        event_increment[20*INCREMENT+:INCREMENT] = INCREMENT'(advance && SYNC_PROFILE == 1);
        event_increment[21*INCREMENT+:INCREMENT] = INCREMENT'(running &&!sources_ready);
        event_increment[22*INCREMENT+:INCREMENT] = INCREMENT'(queue_valid &&!destinations_ready);
        event_increment[23*INCREMENT+:INCREMENT] = INCREMENT'(context_change);
        event_increment[24*INCREMENT+:INCREMENT] = INCREMENT'(o_advance_valid && i_advance_ready);
        event_increment[25*INCREMENT+:INCREMENT] = INCREMENT'(issue && (|result.overflow));
        event_increment[26*INCREMENT+:INCREMENT] = INCREMENT'(issue && (|result.saturated));
        event_increment[27*INCREMENT+:INCREMENT] = INCREMENT'(format_error);
        event_increment[28*INCREMENT+:INCREMENT] = INCREMENT'(corrected);
        event_increment[29*INCREMENT+:INCREMENT] = INCREMENT'(i_body_error || i_body_fatal_error);
        event_increment[30*INCREMENT+:INCREMENT] = INCREMENT'(i_body_idle);
        event_increment[31*INCREMENT+:INCREMENT] = INCREMENT'(i_body_completed);
    end

    performance_counters #(
        .COUNTER_WIDTH(32),
        .NUM_COUNTERS(32),
        .NUM_EVENTS(32),
        .INCREMENT_WIDTH(INCREMENT),
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
