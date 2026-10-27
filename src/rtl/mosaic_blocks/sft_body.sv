`timescale 1ns / 1ps
`default_nettype none
// A reserved, ordered issue queue decouples ingress from one shared FU engine.
// Serial execution is deliberate: local-state dependencies retire before reuse.
module sft_body #(
    parameter INPUT_WIDTH = 16,
    parameter INPUT_FRAC_BITS = 8,
    parameter OUTPUT_WIDTH = 16,
    parameter OUTPUT_FRAC_BITS = 12,
    parameter INTERNAL_WIDTH = 32,
    parameter INTERNAL_FRAC_BITS = 20,
    parameter LUT_ADDRESS_WIDTH = 8,
    parameter LUT_INDEX_FRACTION_WIDTH = 8,
    parameter LUT_BANKS = 4,
    parameter LUT_PIPELINE_DEPTH = 2,
    parameter POLY_COEFFICIENT_WIDTH = 18,
    parameter POLY_MAX_DEGREE = 4,
    parameter POLY_BANKS = 4,
    parameter POLY_EVALUATION_ARCH = 0,
    parameter RECIP_INTERNAL_WIDTH = 24,
    parameter RECIP_INTERNAL_FRAC_BITS = 20,
    parameter RECIP_SEED_ADDRESS_WIDTH = 6,
    parameter RECIP_MAX_ITERATIONS = 2,
    parameter RSQRT_INTERNAL_WIDTH = 28,
    parameter RSQRT_INTERNAL_FRAC_BITS = 22,
    parameter RSQRT_SEED_ADDRESS_WIDTH = 6,
    parameter RSQRT_MAX_ITERATIONS = 2,
    parameter EXP_RANGE_WIDTH = 40,
    parameter EXP_TABLE_ADDRESS_WIDTH = 6,
    parameter EXP_PIPELINE_DEPTH = 5,
    parameter REDUCTION_LANES = 4,
    parameter REDUCTION_ELEMENT_WIDTH = 16,
    parameter REDUCTION_ACC_WIDTH = 48,
    parameter MAX_REDUCTION_ELEMENTS = 1024,
    parameter FU_PROFILE = 1,
    parameter LOCAL_RF_DEPTH = 8,
    parameter LOCAL_RF_READ_PORTS = 2,
    parameter LOCAL_RF_WRITE_PORTS = 1,
    parameter REDUCTION_STATE_DEPTH = 2,
    parameter INPUT_FIFO_DEPTH = 4,
    parameter RESULT_QUEUE_DEPTH = 8,
    parameter MAX_INFLIGHT = 8,
    parameter BYPASS_PROFILE = 1,
    parameter SYNC_PROFILE = 2,
    parameter SUPPORT_SPATIAL_TEMPORAL = 1,
    parameter SUPPORT_INTERPOLATION = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter SUPPORT_LOCAL_CHAINING = 1,
    parameter SUPPORT_FP16 = 0,
    parameter SUPPORT_BF16 = 0,
    parameter REQUIRE_CANONICAL_FORMAT = 1,
    parameter TABLE_PROTECTION = 0,
    parameter COEFFICIENT_PROTECTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    parameter DATA_WIDTH = 64,
    parameter DATA_METADATA_WIDTH = 256,
    parameter DATA_INPUT_PORTS = 2,
    parameter DATA_OUTPUT_PORTS = 2,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONFIG_WORD_COUNT = 270,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter PREDICATE_METADATA_WIDTH = 16,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
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
    localparam int PI = 1,
    localparam int P = 1,
    localparam int PO = 1,
    localparam int EI = 1,
    localparam int E = 32,
    localparam int EO = 1,
    localparam int S = 8,
    localparam int ER = 8,
    localparam int CI = C > 1 ? $clog2(C) : 1
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
    import sft_pkg::*;
    import tile_shell_pkg::*;
    localparam int LA = LUT_ADDRESS_WIDTH;
    localparam int LF = LUT_INDEX_FRACTION_WIDTH;
    localparam int LB = LUT_BANKS;
    localparam int PB = POLY_BANKS;
    localparam int LD = 1 << LA;
    localparam int TABLE_BITS = LD * OUTPUT_WIDTH;
    localparam int COEFFICIENT_BASE = 512 + TABLE_BITS;
    localparam int IMAGE_BITS = COEFFICIENT_BASE + (FU_PROFILE >= 1 ?
        (POLY_MAX_DEGREE + 1) * POLY_COEFFICIENT_WIDTH : 0);
    localparam int LBI = C * LB > 1 ? $clog2(C * LB) : 1;
    localparam int PBI = C * PB > 1 ? $clog2(C * PB) : 1;
    localparam int DI = $clog2(POLY_MAX_DEGREE + 1);
    localparam int RI = $clog2(LOCAL_RF_DEPTH);
    localparam int RA = REDUCTION_ACC_WIDTH;
    localparam int RN = REDUCTION_STATE_DEPTH;
    localparam int EW = REDUCTION_ELEMENT_WIDTH;
    localparam int NL = REDUCTION_LANES;
    localparam int IT = $clog2(RECIP_MAX_ITERATIONS + 1);
    localparam int RT = $clog2(RSQRT_MAX_ITERATIONS + 1);

    // Width-dependent records remain local. A context is an immutable shell image.
    typedef struct packed {
        logic [7:0] operation;
        logic [1:0] datatype;
        logic signed_data;
        logic rounding;
        logic saturate;
        logic interpolate;
        logic base;
        logic false_token;
        logic [1:0] predicate_mode;
        logic [2:0] source_a;
        logic [2:0] source_b;
        logic [7:0] rf_a;
        logic [7:0] rf_b;
        logic [7:0] rf_write;
        logic write_rf;
        logic write_acc;
        logic [2:0] phase;
        logic [2:0] reduction;
        logic [7:0] state_id;
        logic [7:0] bank;
        logic [1:0] quality;
        logic range_error;
        logic [1:0] empty_policy;
        logic terminal;
        logic advance_context;
        logic invalidate;
        logic [15:0] steps;
        logic [7:0] next_context;
        logic [15:0] mask;
        logic [7:0] iterations;
        logic [7:0] degree;
        logic [7:0] shift;
        logic [31:0] model;
        logic [63:0] immediate;
        logic [31:0] x_min;
        logic [31:0] x_max;
        logic [31:0] epsilon;
        logic [15:0] table_id;
        logic [15:0] polynomial_id;
        logic [7:0] source_format;
        logic [7:0] result_format;
        logic [7:0] output_mask;
        logic [4:0] opcode;
        logic dynamic_phase;
        logic monitor;
        logic select_condition;
    } context_t;

    function automatic context_t decode(input logic [IM-1:0] image);
        context_t c;
        c.operation = image[8+:8];
        c.datatype = image[16+:2];
        c.signed_data = image[18];
        c.rounding = image[19];
        c.saturate = image[20];
        c.interpolate = image[21];
        c.base = image[22];
        c.false_token = image[23];
        c.predicate_mode = image[24+:2];
        c.source_a = image[26+:3];
        c.source_b = image[29+:3];
        c.rf_a = image[32+:8];
        c.rf_b = image[40+:8];
        c.rf_write = image[48+:8];
        c.write_rf = image[56];
        c.write_acc = image[57];
        c.phase = image[58+:3];
        c.reduction = image[61+:3];
        c.state_id = image[64+:8];
        c.bank = image[72+:8];
        c.quality = image[80+:2];
        c.range_error = image[82];
        c.empty_policy = image[83+:2];
        c.terminal = image[85];
        c.advance_context = image[86];
        c.invalidate = image[87];
        c.steps = image[88+:16];
        c.next_context = image[104+:8];
        c.mask = image[112+:16];
        c.iterations = image[128+:8];
        c.degree = image[136+:8];
        c.shift = image[144+:8];
        c.model = image[152+:32];
        c.immediate = image[192+:64];
        c.x_min = image[256+:32];
        c.x_max = image[288+:32];
        c.epsilon = image[320+:32];
        c.table_id = image[352+:16];
        c.polynomial_id = image[368+:16];
        c.source_format = image[384+:8];
        c.result_format = image[392+:8];
        c.output_mask = image[400+:8];
        c.opcode = image[408+:5];
        c.dynamic_phase = image[413];
        c.monitor = image[414];
        c.select_condition = image[415];
        return c;
    endfunction

    function automatic logic edge_legal(input logic [2:0] source);
        return source < 2 || source == SFT_ZERO || source == SFT_IMMEDIATE ||
            (SUPPORT_LOCAL_CHAINING == 1 && (source == SFT_ACC ||
            (BYPASS_PROFILE >= 1 && (source == SFT_RF_A || source == SFT_RF_B)) ||
            (BYPASS_PROFILE == 2 && source == SFT_PREVIOUS)));
    endfunction

    function automatic logic legal(input logic [IM-1:0] image, input logic [CI-1:0] context_id);
        context_t c;
        c = decode(image);
        return (^image !== 1'bx) && image[7:0] == 1 && image[191:184] == 0 &&
            image[511:416] == 0 && (image >> IMAGE_BITS) == 0 && c.operation <= 9 &&
            c.datatype <= 2 && (c.datatype != 0 || c.signed_data) &&
            (c.datatype != 1 ||!c.signed_data) && c.predicate_mode <= 2 &&
            (!c.false_token || SUPPORT_PREDICATED_TOKEN == 1) &&
            (!c.saturate || SUPPORT_SATURATION == 1) &&
            (!c.interpolate || SUPPORT_INTERPOLATION == 1) &&
            (!(c.write_rf || c.write_acc) || SUPPORT_LOCAL_CHAINING == 1) &&
            edge_legal(c.source_a) && edge_legal(c.source_b) &&
            c.rf_a < LOCAL_RF_DEPTH && c.rf_b < LOCAL_RF_DEPTH &&
            c.rf_write < LOCAL_RF_DEPTH && c.state_id < RN &&
            c.quality <= 2 && c.empty_policy <= 2 && c.phase <= REDUCE_READ &&
            c.reduction <= REDUCE_MAX && (c.mask >> NL) == 0 && c.steps != 0 &&
            (!c.advance_context || (SUPPORT_SPATIAL_TEMPORAL == 1 &&
                !c.terminal && c.next_context < C && c.next_context > context_id)) &&
            (c.output_mask >> NO) == 0 && c.shift < D &&
            c.source_format <= 3 && c.result_format <= 3 &&
            c.model == (32'h53460000 | (32'(c.quality) << 8) | 32'(c.operation)) &&
            (c.operation != SFT_MULTIPLY || FU_PROFILE >= 1) &&
            (c.operation != SFT_LUT || c.bank < LB) &&
            (c.operation != SFT_POLYNOMIAL || (FU_PROFILE >= 1 && c.bank < PB &&
                c.degree <= POLY_MAX_DEGREE && c.signed_data &&
                c.shift < INTERNAL_WIDTH && c.shift < 32)) &&
            (c.operation != SFT_RECIPROCAL || (FU_PROFILE >= 2 &&
                c.iterations <= RECIP_MAX_ITERATIONS && c.iterations == c.quality)) &&
            (c.operation != SFT_RSQRT || (FU_PROFILE >= 2 &&
                c.iterations <= RSQRT_MAX_ITERATIONS && c.iterations == c.quality)) &&
            (c.operation != SFT_EXP || FU_PROFILE == 3) &&
            (c.operation != SFT_ALU || (c.opcode <= 20 &&
                (!c.saturate || c.opcode == 0 || c.opcode == 1 || c.opcode == 20))) &&
            (c.operation != SFT_ACCUMULATOR || c.opcode <= 3);
    endfunction

    context_t ctx;
    context_t programming_context;
    assign ctx = decode(o_body_context_image);
    wire reset_known = i_rstb === 1'b1;
    wire clear_private = o_body_flush === 1'b1 || i_execution_state == TILE_UNALLOCATED ||
        i_power_state == POWER_OFF;
    wire live = reset_known &&!clear_private &&!i_isolate;

    typedef struct packed {
        logic started;
        logic complete;
        logic advance_context;
        logic fatal;
        logic [7:0] error_code;
        logic [15:0] issued;
        logic [15:0] retired;
        logic [5:0] inflight;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [31:0] header_witness;
        engine_phase_t phase;
        logic [NI*D-1:0] inputs;
        logic [M-1:0] metadata;
        logic predicate;
        logic [2:0] reduction_phase;
        logic [15:0] tag;
        logic [D-1:0] result;
        logic [15:0] flags;
        logic [15:0] count;
        logic empty_result;
        logic suppress;
        logic [LOCAL_RF_DEPTH-1:0] rf_valid;
        logic previous_valid;
        logic [D-1:0] previous;
        logic [7:0] previous_format;
        logic previous_signed;
        logic [O-1:0] previous_owner;
        logic [K-1:0] previous_kernel;
        logic [V-1:0] previous_version;
    } control_t;

    control_t q;
    control_t n;
    wire control_bad;
    wire control_corrected;
    logic fatal_latch;
    wire [31:0] header_witness = o_body_context_image[31:0] ^
        o_body_context_image[63:32] ^ o_body_context_image[95:64] ^
        o_body_context_image[127:96] ^ o_body_context_image[159:128] ^
        o_body_context_image[191:160] ^ o_body_context_image[223:192] ^
        o_body_context_image[255:224] ^ o_body_context_image[287:256] ^
        o_body_context_image[319:288] ^ o_body_context_image[351:320] ^
        o_body_context_image[383:352] ^ o_body_context_image[415:384];
    wire context_change = o_body_context_active && (q.context_id != o_body_context_id ||
        q.version != o_body_context_version);
    wire enabled = live && i_clock_enable === 1'b1 &&!q.fatal &&!fatal_latch &&!control_bad;
    wire executing = enabled && q.started &&!o_body_start &&!context_change &&!q.complete &&
        !q.advance_context && (i_execution_state == TILE_ACTIVE ||
        i_execution_state == TILE_INPUT_STALL || i_execution_state == TILE_OUTPUT_STALL ||
        i_execution_state == TILE_SUSPENDING || i_execution_state == TILE_DRAINING);
    wire fatal_now;
    wire [7:0] fatal_code;

    always_ff @(posedge i_clk) begin
        if (i_rstb === 1'b0) fatal_latch <= 1'b0;
        else if (reset_known && (control_bad || fatal_now)) fatal_latch <= 1'b1;
    end

    tile_shell_state #(.WIDTH($bits(control_t)),
        .PROTECTION(CONTROL_PROTECTION)) u_control (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_enable(reset_known && (clear_private || context_change || o_body_start ||
            i_clock_enable === 1'b1)),
        .i_data(n),
        .o_data(q),
        .o_bad(control_bad),
        .o_corrected(control_corrected)
    );

    // Programming owns only the context's physical bank slice. Active slices are
    // immutable; a failed validation can damage no other context's bank image.
    localparam int PGI = LA + 1 > $clog2(POLY_MAX_DEGREE + 1) ?
        LA + 1 : $clog2(POLY_MAX_DEGREE + 1);

    typedef struct packed {
        program_phase_t phase;
        program_phase_t return_phase;
        logic poly;
        logic [7:0] bank;
        logic [PGI-1:0] index;
        logic [IM-1:0] image;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic legal_image;
    } programming_t;

    programming_t programming;
    programming_t programming_next;
    wire program_bad;
    wire program_corrected;
    wire [2:0] program_phase = programming.phase;
    wire [2:0] program_return = programming.return_phase;
    wire program_poly = programming.poly;
    wire [7:0] program_bank = programming.bank;
    wire [PGI-1:0] program_index = programming.index;
    wire [IM-1:0] program_image = programming.image;
    wire [CI-1:0] program_context = programming.context_id;
    wire [V-1:0] program_version = programming.version;
    wire program_legal = programming.legal_image;
    wire program_valid = reset_known &&!program_bad &&
        (program_phase == PROGRAM_INVALIDATE || program_phase == PROGRAM_WRITE ||
        program_phase == PROGRAM_COMMIT);
    wire [1:0] program_command = program_phase == PROGRAM_INVALIDATE ? 2'd3 :
        program_phase == PROGRAM_COMMIT ? 2'd2 : 2'd0;
    wire lut_program_ready;
    wire lut_program_response;
    wire lut_program_error;
    wire [C*LB-1:0] lut_bank_valid;
    wire [C*PB-1:0] poly_bank_valid;
    wire poly_program_ready;
    wire poly_program_response;
    wire poly_program_error;
    wire program_ready = program_poly ? poly_program_ready : lut_program_ready;
    wire program_response = program_poly ? poly_program_response : lut_program_response;
    wire program_error = program_poly ? poly_program_error : lut_program_error;
    assign programming_context = decode(program_image);
    assign i_body_validate_ready = reset_known && program_phase == PROGRAM_IDLE &&!program_bad;
    assign i_body_validate_result_valid = reset_known && (program_phase == PROGRAM_DONE ||
        program_bad);
    assign i_body_validate_context_id = program_context;
    assign i_body_validate_context_version = program_version;
    assign i_body_validate_legal = program_legal &&!program_bad;
    assign i_body_validate_error_code = program_legal &&!program_bad ? 8'd0 : 8'(SFT_ERR_CONTEXT);

    always @* begin
        programming_next = programming;

        if (i_rstb === 1'b0 || (reset_known && clear_private)) begin
            programming_next.phase = PROGRAM_IDLE;
            programming_next.return_phase = PROGRAM_IDLE;
            programming_next.poly = 1'b0;
            programming_next.bank = '0;
            programming_next.index = '0;
            programming_next.context_id = '0;
            programming_next.version = '0;
            programming_next.legal_image = 1'b0;
        end else if (reset_known &&!program_bad) begin
            if (o_body_validate_valid === 1'b1 && i_body_validate_ready) begin
                programming_next.image = o_body_validate_context_image;
                programming_next.context_id = o_body_validate_context_id;
                programming_next.version = o_body_validate_context_version;
                programming_next.poly = o_body_validate_context_image[8+:8] == SFT_POLYNOMIAL;
                programming_next.bank = o_body_validate_context_image[72+:8];
                programming_next.index = '0;
                programming_next.legal_image = legal(o_body_validate_context_image,
                    o_body_validate_context_id) &&
                    (&o_body_validate_word_valid) &&
                    !(o_body_context_active && o_body_validate_context_id == o_body_context_id);
                programming_next.phase = legal(o_body_validate_context_image,
                    o_body_validate_context_id) &&
                    (&o_body_validate_word_valid) &&
                    !(o_body_context_active && o_body_validate_context_id == o_body_context_id) ?
                    (o_body_validate_context_image[8+:8] == SFT_LUT ?
                    (lut_bank_valid[o_body_validate_context_id*LB +
                        o_body_validate_context_image[72+:8]] ? PROGRAM_INVALIDATE : PROGRAM_WRITE)
                            :
                    o_body_validate_context_image[8+:8] == SFT_POLYNOMIAL ?
                    (poly_bank_valid[o_body_validate_context_id*PB +
                        o_body_validate_context_image[72+:8]] ? PROGRAM_INVALIDATE : PROGRAM_WRITE)
                            :
                    PROGRAM_DONE) : PROGRAM_DONE;
            end else if (program_valid && program_ready) begin
                programming_next.return_phase = programming.phase;
                programming_next.phase = PROGRAM_RESPONSE;
            end else if (program_phase == PROGRAM_RESPONSE && program_response) begin
                if (program_error) begin
                    programming_next.legal_image = 1'b0;
                    programming_next.phase = PROGRAM_DONE;
                end else if (program_return == PROGRAM_INVALIDATE) begin
                    programming_next.index = '0;
                    programming_next.phase = PROGRAM_WRITE;
                end else if (program_return == PROGRAM_WRITE) begin
                    if (program_index == (program_poly ? POLY_MAX_DEGREE : LD - 1))
                        programming_next.phase = PROGRAM_COMMIT;
                    else begin
                        programming_next.index = program_index + 1'b1;
                        programming_next.phase = PROGRAM_WRITE;
                    end
                end else programming_next.phase = PROGRAM_DONE;
            end else if (program_phase == PROGRAM_DONE && o_body_validate_result_ready === 1'b1)
                programming_next.phase = PROGRAM_IDLE;
        end
    end

    tile_shell_state #(.WIDTH($bits(programming_t)),
        .PROTECTION(CONTROL_PROTECTION)) u_programming (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_enable(reset_known &&!program_bad),
        .i_data(programming_next),
        .o_data(programming),
        .o_bad(program_bad),
        .o_corrected(program_corrected)
    );

    // Each input remains ordered. Only actually referenced external operands pop.
    wire [NI-1:0] input_valid;
    wire [NI-1:0] input_ready;
    wire [NI*(D+M)-1:0] input_data;
    wire [NI-1:0] input_bad;
    wire [NI*32-1:0] input_counts;
    wire need_b = ctx.operation == SFT_MULTIPLY ||
        (ctx.operation == SFT_ALU && ctx.opcode != 5 && ctx.opcode != 16 && ctx.opcode != 20);
    wire need_a = !(ctx.operation == SFT_ALU && ctx.opcode == 17) &&
        !(ctx.operation == SFT_ACCUMULATOR && (ctx.opcode == 0 || ctx.opcode == 3));
    logic [NI-1:0] required;

    always @* begin
        required = '0;

        if (need_a && ctx.source_a < NI) required[ctx.source_a] = 1'b1;

        if (need_b && ctx.source_b < NI) required[ctx.source_b] = 1'b1;
    end

    // The shell stops new external admission for suspend/drain. Its already
    // accepted operands must still be delivered into the body and retired.
    wire allow_admission = executing && q.issued < ctx.steps;
    for (genvar p = 0; p < NI; p++) begin : g_input
        tile_shell_queue #(.WIDTH(D + M),
            .DEPTH(SYNC_PROFILE == 0 ? 0 : INPUT_FIFO_DEPTH),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_flush(clear_private || context_change),
            .i_admit(live && allow_admission && required[p] &&
                input_counts[p*32+:32] + q.issued < ctx.steps),
            .i_deliver(enabled),
            .i_valid(o_body_data_in_valid[p] === 1'b1),
            .o_ready(i_body_data_in_ready[p]),
            .i_data({o_body_data_in_metadata[p*M+:M], o_body_data_in_payload[p*D+:D]}),
            .o_valid(input_valid[p]),
            .i_ready(input_ready[p]),
            .o_data(input_data[p*(D+M)+:(D+M)]),
            .o_bad(input_bad[p]),
            .o_corrected(),
        .o_count(input_counts[p*32+:32])
        );
    end

    wire predicate_valid;
    wire predicate_ready;
    wire [PM:0] predicate_data;
    wire predicate_bad;
    wire [31:0] predicate_count;
    tile_shell_queue #(
        .WIDTH(PM + 1),
        .DEPTH(SYNC_PROFILE == 0 ? 0 : INPUT_FIFO_DEPTH),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_predicate_queue (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_flush(clear_private || context_change),
        .i_admit(live && allow_admission && ctx.predicate_mode == 1 &&
            predicate_count + q.issued < ctx.steps),
        .i_deliver(enabled),
        .i_valid(o_body_predicate_in_valid[0] === 1'b1),
        .o_ready(i_body_predicate_in_ready[0]),
        .i_data({o_body_predicate_in_metadata, o_body_predicate_in_payload}),
        .o_valid(predicate_valid),
        .i_ready(predicate_ready),
        .o_data(predicate_data),
        .o_bad(predicate_bad),
        .o_corrected(),
        .o_count(predicate_count)
    );

    typedef struct packed {
        logic [NI*D-1:0] inputs;
        logic [M-1:0] metadata;
        logic predicate;
        logic [2:0] reduction_phase;
        logic [15:0] tag;
    } request_t;

    request_t offered;
    request_t request;
    logic [M-1:0] offered_metadata;
    logic [NI*D-1:0] offered_inputs;
    wire [15:0] active_mask = ctx.mask;
    logic operands_known;
    logic operands_match;
    logic operands_present;
    wire joined_valid;
    wire [NI:0] joined_ready;
    wire [NI:0] join_required = {ctx.predicate_mode == 1, required};

    stream_join #(
        .NUM_INPUTS(NI + 1),
        .DATA_WIDTH(1),
        .HAS_REQUIRED_MASK(1)
    ) u_join (
        .i_valid({predicate_valid, input_valid}),
        .o_ready(joined_ready),
        .i_data({(NI + 1){1'b0}}),
        .i_required(join_required),
        .o_valid(joined_valid),
        .i_ready(issue),
        .o_data(),
        .o_required()
    );

    always @* begin
        offered = '0;
        offered_metadata = '0;
        offered_inputs = '0;
        offered_metadata[0+:CI] = o_body_context_id;
        offered_metadata[CI+:V] = o_body_context_version;
        offered.predicate = ctx.predicate_mode == 0 ||
            (ctx.predicate_mode == 1 && predicate_data[0]);
        offered.tag = q.issued;
        operands_known = 1'b1;
        operands_present = joined_valid || join_required == 0;

        for (int p = NI - 1; p >= 0; p--) begin
            offered_inputs[p*D+:D] = input_data[p*(D+M)+:D];

            if (required[p]) begin
                offered_metadata = input_data[p*(D+M)+D+:M];

                if (^input_data[p*(D+M)+D+:M] === 1'bx) operands_known = 1'b0;

                if (ctx.operation == SFT_REDUCE) begin
                    for (int lane = 0; lane < NL; lane++)
                        if (active_mask[lane] &&
                            ^input_data[p*(D+M)+lane*EW+:EW] === 1'bx)
                            operands_known = 1'b0;
                end else if (^input_data[p*(D+M)+:D] === 1'bx) operands_known = 1'b0;
            end
        end

        if (ctx.predicate_mode == 1 && ^predicate_data === 1'bx) operands_known = 1'b0;

        if (ctx.operation == SFT_REDUCE) begin
            for (int p = 0; p < NI; p++) begin
                offered_inputs[p*D+:D] = '0;

                for (int lane = 0; lane < NL; lane++)
                    if (active_mask[lane]) offered_inputs[p*D+lane*EW+:EW] =
                        input_data[p*(D+M)+lane*EW+:EW];
            end
        end

        operands_match = 1'b1;

        for (int p = 0; p < NI; p++)
            if (required[p] && input_data[p*(D+M)+D+:M] !== offered_metadata)
                operands_match = 1'b0;

        if (!offered.predicate) offered_inputs = '0;

        offered.inputs = offered_inputs;
        offered.metadata = offered_metadata;
        offered.reduction_phase = ctx.dynamic_phase ? offered_metadata[32+:3] : ctx.phase;
    end

    wire request_ready;
    wire request_valid;
    wire request_pop;
    wire request_bad;
    wire [31:0] request_count;
    wire issue = executing && q.issued < ctx.steps && q.inflight < MAX_INFLIGHT &&
        operands_present && operands_known && request_ready &&!fatal_now;
    assign input_ready = joined_ready[0+:NI];
    assign predicate_ready = joined_ready[NI];

    tile_shell_queue #(
        .WIDTH($bits(request_t)),
        .DEPTH(RESULT_QUEUE_DEPTH),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_requests (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_flush(clear_private || context_change),
        .i_admit(enabled),
        .i_deliver(enabled),
        .i_valid(issue),
        .o_ready(request_ready),
        .i_data(offered),
        .o_valid(request_valid),
        .i_ready(request_pop),
        .o_data(request),
        .o_count(request_count),
        .o_bad(request_bad),
        .o_corrected()
    );

    assign request_pop = executing && q.phase == ENGINE_IDLE &&!fatal_now;

    // Local RF entries include format and full allocation/version identity.
    typedef struct packed {
        logic [O-1:0] owner;
        logic [K-1:0] kernel;
        logic [V-1:0] version;
        logic [7:0] format_id;
        logic signed_data;
        logic [D-1:0] data;
    } scalar_state_t;

    localparam int RW = $bits(scalar_state_t);
    localparam int RC = RW + (CONTROL_PROTECTION == 0 ? 0 :
        CONTROL_PROTECTION == 1 ? 1 : hamming_bits(RW) + 1);

    function automatic int hamming_bits(input int width);
        int bits;
        bits = 1;

        while ((64'd1 << bits) < 64'(width) + bits + 1) bits++;

        return bits;
    endfunction

    scalar_state_t rf_a;
    scalar_state_t rf_b;
    wire [2*RW-1:0] rf_decoded;
    assign rf_a = rf_decoded[0+:RW];
    assign rf_b = rf_decoded[RW+:RW];
    scalar_state_t rf_write;
    wire [RC-1:0] rf_code;
    wire [2*RC-1:0] rf_received;
    wire [1:0] rf_bad;
    wire commit;
    wire [LOCAL_RF_DEPTH-1:0] rf_valid_bits = q.rf_valid;
    logic [LOCAL_RF_DEPTH-1:0] next_rf_valid;
    wire write_rf = commit && q.predicate &&!q.flags[0] && ctx.write_rf;
    assign rf_write = {i_owner, i_kernel, o_body_context_version,
        ctx.result_format, ctx.signed_data, q.result};

    tile_shell_codec #(
        .WIDTH(RW),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_rf_encoder (
        .i_data(rf_write),
        .o_code(rf_code),
        .i_code({RC{1'b0}}),
        .o_data(),
        .o_bad(),
        .o_corrected()
    );

    register_file #(
        .DATA_WIDTH(RC),
        .DEPTH(LOCAL_RF_DEPTH),
        .NUM_READ_PORTS(2),
        .NUM_WRITE_PORTS(1)
    ) u_rf (
        .i_clk(i_clk),
        .i_read_enable({2{enabled && q.predicate && q.phase == ENGINE_DISPATCH}}),
        .i_read_address({RI'(ctx.rf_b), RI'(ctx.rf_a)}),
        .o_read_data(rf_received),
        .i_write_enable(write_rf),
        .i_write_address(RI'(ctx.rf_write)),
        .i_write_data(rf_code)
    );

    for (genvar r = 0; r < 2; r++) begin : g_rf_decode
        tile_shell_codec #(
            .WIDTH(RW),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_codec (
            .i_data({RW{1'b0}}),
            .o_code(),
            .i_code(rf_received[r*RC+:RC]),
            .o_data(rf_decoded[r*RW+:RW]),
            .o_bad(rf_bad[r]),
            .o_corrected()
        );
    end

    wire [D-1:0] accumulator_data;
    scalar_state_t accumulator_owner;
    scalar_state_t accumulator_owner_next;
    wire accumulator_bad;
    logic accumulator_valid;
    wire write_acc = commit && q.predicate &&!q.flags[0] &&
        (ctx.write_acc || ctx.operation == SFT_ACCUMULATOR && ctx.opcode != 3);

    accumulator #(.ACC_WIDTH(D)) u_accumulator (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0 &&!clear_private),
        .i_clock_enable(enabled),
        .i_valid(write_acc),
        .i_command(2'd1),
        .i_lane_mask(1'b1),
        .i_data(q.result),
        .i_signed(ctx.signed_data),
        .i_saturate(1'b0),
        .o_data(accumulator_data),
        .o_valid(),
        .o_illegal_operation(),
        .o_updated_mask(),
        .o_state_valid(),
        .o_state_signed(),
        .o_carry(),
        .o_borrow(),
        .o_overflow(),
        .o_saturated(),
        .o_zero(),
        .o_negative()
    );

    assign accumulator_owner_next = rf_write;

    tile_shell_state #(
        .WIDTH(RW),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_accumulator_owner (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0 &&!clear_private),
        .i_enable(write_acc),
        .i_data(accumulator_owner_next),
        .o_data(accumulator_owner),
        .o_bad(accumulator_bad),
        .o_corrected()
    );

    always_ff @(posedge i_clk) begin
        if (i_rstb === 1'b0) accumulator_valid <= 1'b0;
        else if (reset_known) begin
            if (clear_private || context_change && ctx.invalidate) accumulator_valid <= 1'b0;
            else if (write_acc) accumulator_valid <= 1'b1;
        end
    end

    logic [8*D-1:0] sources;
    logic [7:0] source_valid;
    wire [2*D-1:0] selected;
    wire [1:0] selected_valid;
    wire [1:0] selection_error;
    wire dispatch = executing && q.phase == ENGINE_DISPATCH;

    always @* begin
        sources = '0;
        source_valid = '1;
        sources[0+:NI*D] = q.inputs;
        sources[2*D+:D] = rf_a.data;
        sources[3*D+:D] = rf_b.data;
        sources[4*D+:D] = accumulator_data;
        sources[5*D+:D] = q.previous;
        sources[6*D+:D] = D'(ctx.immediate);
        source_valid[2] = rf_valid_bits[ctx.rf_a] &&!rf_bad[0] &&
            rf_a.owner == i_owner && rf_a.kernel == i_kernel &&
            rf_a.version == o_body_context_version && rf_a.format_id == ctx.source_format &&
            rf_a.signed_data == ctx.signed_data;
        source_valid[3] = rf_valid_bits[ctx.rf_b] &&!rf_bad[1] &&
            rf_b.owner == i_owner && rf_b.kernel == i_kernel &&
            rf_b.version == o_body_context_version && rf_b.format_id == ctx.source_format &&
            rf_b.signed_data == ctx.signed_data;
        source_valid[4] = accumulator_valid &&!accumulator_bad &&
            accumulator_owner.data == accumulator_data && accumulator_owner.owner == i_owner &&
            accumulator_owner.kernel == i_kernel &&
            accumulator_owner.version == o_body_context_version &&
            accumulator_owner.format_id == ctx.source_format &&
            accumulator_owner.signed_data == ctx.signed_data;
        source_valid[5] = q.previous_valid && q.previous_format == ctx.source_format &&
            q.previous_signed == ctx.signed_data && q.previous_owner == i_owner &&
            q.previous_kernel == i_kernel && q.previous_version == o_body_context_version;
    end

    localparam logic [15:0] CONNECTIVITY = BYPASS_PROFILE == 0 ? 16'hd3d3 :
        BYPASS_PROFILE == 1 ? 16'hdfdf : 16'hffff;

    bypass_network #(
        .DATA_WIDTH(D),
        .NUM_SOURCES(8),
        .NUM_DESTINATIONS(2),
        .CONNECTIVITY_MASK(CONNECTIVITY)
    ) u_sources (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_source_data(sources),
        .i_source_valid(source_valid),
        .i_destination_enable({dispatch && need_b && q.predicate, dispatch && need_a &&
            q.predicate}),
        .i_select({ctx.source_b, ctx.source_a}),
        .i_capture_enable(2'b11),
        .i_flush(clear_private),
        .o_destination_data(selected),
        .o_destination_valid(selected_valid),
        .o_selection_error(selection_error)
    );

    wire [D-1:0] a = selected[0+:D];
    wire [D-1:0] b = selected[D+:D];
    wire [D-1:0] math_data;
    wire [15:0] math_flags;
    wire [15:0] math_count;

    sft_datapath #(
        .D(D),
        .I(INPUT_WIDTH),
        .OW(OUTPUT_WIDTH),
        .EW(EW),
        .NL(NL),
        .RA(RA),
        .GENERAL_MULTIPLY(FU_PROFILE >= 1),
        .SUPPORT_SATURATION(SUPPORT_SATURATION)
    ) u_math (
        .i_enable(dispatch && q.predicate),
        .i_operation(ctx.operation == SFT_ACCUMULATOR ? 8'(SFT_ALU) : ctx.operation),
        .i_opcode(ctx.operation == SFT_ACCUMULATOR ? 5'd0 : ctx.opcode),
        .i_a(ctx.operation == SFT_ACCUMULATOR ? accumulator_data : a),
        .i_b(ctx.operation == SFT_ACCUMULATOR ? a : b),
        .i_signed(ctx.signed_data),
        .i_saturate(ctx.saturate),
        .i_round(ctx.rounding),
        .i_select(ctx.select_condition),
        .i_shift(ctx.shift),
        .i_mask(ctx.mask[0+:NL]),
        .i_reduction(ctx.reduction),
        .o_data(math_data),
        .o_flags(math_flags),
        .o_count(math_count)
    );

    // Persistent exact reductions retain operation, format and ownership together.
    typedef struct packed {
        logic valid_state;
        logic [O-1:0] owner;
        logic [K-1:0] kernel;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic signed_data;
        logic [2:0] operation;
        logic [7:0] format_id;
        logic [RA-1:0] value;
        logic [15:0] count;
    } reduction_state_t;

    localparam int RS = $bits(reduction_state_t);
    wire [RN*RS-1:0] reduction_values;
    wire [RN-1:0] reduction_bad;
    logic [D-1:0] reduction_result;
    logic [15:0] reduction_count;
    logic reduction_legal;
    logic reduction_empty;
    reduction_state_t red;
    assign red = reduction_values[ctx.state_id*RS+:RS];
    wire red_existing = q.reduction_phase == REDUCE_UPDATE || q.reduction_phase == REDUCE_END ||
        q.reduction_phase == REDUCE_READ;
    wire [16:0] reduction_total = 17'(red_existing ? red.count : 0) +
        17'(q.reduction_phase == REDUCE_READ || q.reduction_phase == REDUCE_CLEAR ?
            0 : math_count);
    wire reduction_count_limit = reduction_total > MAX_REDUCTION_ELEMENTS;
    wire red_update = commit && q.predicate &&!q.flags[0] && ctx.operation == SFT_REDUCE &&
        q.reduction_phase != REDUCE_BEAT && q.reduction_phase != REDUCE_READ;

    always @* begin
        reduction_result = math_data;
        reduction_count = math_count;
        reduction_legal = q.reduction_phase <= REDUCE_READ;

        if (red_existing) begin
            reduction_legal = reduction_legal && red.valid_state &&
                !reduction_bad[ctx.state_id] && red.owner == i_owner && red.kernel == i_kernel &&
                red.context_id == o_body_context_id && red.version == o_body_context_version &&
                red.operation == ctx.reduction && red.signed_data == ctx.signed_data &&
                red.format_id == ctx.source_format;

            if (q.reduction_phase == REDUCE_READ) begin
                reduction_result = ctx.signed_data && ctx.reduction != REDUCE_SUMSQ ?
                    D'($signed(red.value)) : D'(red.value);
                reduction_count = red.count;
            end else begin
                reduction_count = red.count + math_count;

                if (ctx.reduction < REDUCE_MIN)
                    reduction_result = (ctx.signed_data && ctx.reduction != REDUCE_SUMSQ ?
                        D'($signed(red.value)) : D'(red.value)) + math_data;
                else if (math_count == 0) reduction_result = D'(red.value);
                else if (red.count != 0) begin
                    if (ctx.signed_data)
                        reduction_result = ($signed(math_data) < $signed(D'($signed(red.value))))
                            == (ctx.reduction == REDUCE_MIN) ? math_data :
                            D'($signed(red.value));
                    else reduction_result = (math_data < D'(red.value)) ==
                        (ctx.reduction == REDUCE_MIN) ? math_data : D'(red.value);
                end
            end
        end

        if (q.reduction_phase == REDUCE_CLEAR) begin
            reduction_result = '0;
            reduction_count = '0;
        end

        reduction_legal = reduction_legal &&!reduction_count_limit;
        reduction_empty = reduction_count == 0;
    end

    for (genvar r = 0; r < RN; r++) begin : g_reduction_state
        reduction_state_t stored;
        reduction_state_t next_value;
        assign reduction_values[r*RS+:RS] = stored;

        always @* begin
            next_value = stored;

            if (clear_private || context_change && ctx.invalidate) next_value = '0;
            else if (red_update && ctx.state_id == r) begin
                next_value.valid_state = q.reduction_phase != REDUCE_CLEAR;
                next_value.owner = i_owner;
                next_value.kernel = i_kernel;
                next_value.context_id = o_body_context_id;
                next_value.version = o_body_context_version;
                next_value.signed_data = ctx.signed_data;
                next_value.operation = ctx.reduction;
                next_value.format_id = ctx.source_format;
                next_value.value = q.result[0+:RA];
                next_value.count = q.count;
            end
        end

        tile_shell_state #(
            .WIDTH($bits(reduction_state_t)),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_state (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_enable(reset_known && (clear_private || context_change || red_update)),
            .i_data(next_value),
            .o_data(stored),
            .o_bad(reduction_bad[r]),
            .o_corrected()
        );
    end

    // Native ready/valid FUs retain their own tagged result and numerical flags.
    wire [6:0] fu_ready;
    wire [6:0] fu_valid;
    wire [6:0] fu_fatal;
    wire [7*OUTPUT_WIDTH-1:0] fu_data;
    wire [7*16-1:0] fu_flags;
    wire [7*8-1:0] fu_context;
    wire [7*16-1:0] fu_tag;
    wire native_request = dispatch && q.predicate &&!fatal_now;
    wire native_accept = native_request && ctx.operation >= SFT_LUT &&
        ctx.operation <= SFT_EXP && fu_ready[ctx.operation];
    wire native_consume = executing && q.phase == ENGINE_WAIT;
    assign fu_ready[1:0] = '0;
    assign fu_valid[1:0] = '0;
    assign fu_fatal[1:0] = '0;
    assign fu_data[0+:2*OUTPUT_WIDTH] = '0;
    assign fu_flags[0+:32] = '0;
    assign fu_context[0+:16] = '0;
    assign fu_tag[0+:32] = '0;
    wire lut_low;
    wire lut_high;
    wire lut_interpolated;
    wire lut_error;
    wire [3:0] lut_error_code;

    lut_unit #(
        .ADDRESS_WIDTH(LA),
        .OUTPUT_WIDTH(OUTPUT_WIDTH),
        .INDEX_FRACTION_WIDTH(LF),
        .NUM_BANKS(C * LB),
        .SUPPORT_INTERPOLATION(SUPPORT_INTERPOLATION),
        .LOOKUP_PIPELINE_DEPTH(LUT_PIPELINE_DEPTH),
        .TABLE_VERSION_WIDTH(V),
        .CONTEXT_ID_WIDTH(8),
        .LOOKUP_TAG_WIDTH(16),
        .BUFFER_PROTECTION(TABLE_PROTECTION)
    ) u_lut (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_drain('0),
        .i_flush(clear_private),
        .i_error_clear('0),
        .i_lookup_valid(native_request && ctx.operation == SFT_LUT),
        .i_lookup_coordinate(a[0+:(1+LA+LF)]),
        .i_lookup_bank(LBI'(q.context_id * LB + ctx.bank)),
        .i_lookup_index_signed(ctx.signed_data),
        .i_lookup_output_signed(ctx.signed_data),
        .i_lookup_interpolate(ctx.interpolate),
        .i_lookup_round_mode(ctx.rounding),
        .i_lookup_predicate(1'b1),
        .i_lookup_context_id(8'(q.context_id)),
        .i_lookup_tag(q.tag),
        .i_result_ready(native_consume),
        .i_program_valid(program_valid &&!program_poly),
        .i_program_command(program_command),
        .i_program_bank(LBI'(program_context * LB + program_bank)),
        .i_program_address(program_index[0+:LA]),
        .i_program_write_data(program_image[512 + program_index * OUTPUT_WIDTH+:OUTPUT_WIDTH]),
        .i_program_table_id(programming_context.table_id),
        .i_program_quality_id(4'(programming_context.quality)),
        .i_program_response_ready(reset_known && program_phase == PROGRAM_RESPONSE),
        .o_result_valid(fu_valid[2]),
        .o_result_data(fu_data[2*OUTPUT_WIDTH+:OUTPUT_WIDTH]),
        .o_result_context_id(fu_context[2*8+:8]),
        .o_result_tag(fu_tag[2*16+:16]),
        .o_fatal_error(fu_fatal[2]),
        .o_lookup_ready(fu_ready[2]),
        .o_result_clipped_low(lut_low),
        .o_result_clipped_high(lut_high),
        .o_result_interpolated(lut_interpolated),
        .o_result_error(lut_error),
        .o_result_error_code(lut_error_code),
        .o_program_ready(lut_program_ready),
        .o_program_response_valid(lut_program_response),
        .o_bank_valid(lut_bank_valid),
        .o_program_response_error(lut_program_error)
    );

    assign fu_flags[2*16+:16] = {8'd0, lut_high, lut_low, lut_interpolated,
        4'd0, lut_error};

    if (FU_PROFILE >= 1) begin : g_polynomial
        wire clip_low;
        wire clip_high;
        wire internal_saturated;
        wire output_saturated;
        wire inexact;
        wire result_error;

        polynomial_unit #(
            .INPUT_WIDTH(INPUT_WIDTH),
            .COEFFICIENT_WIDTH(POLY_COEFFICIENT_WIDTH),
            .ACCUMULATOR_WIDTH(INTERNAL_WIDTH),
            .OUTPUT_WIDTH(OUTPUT_WIDTH),
            .FRACTION_WIDTH(INPUT_FRAC_BITS),
            .MAX_DEGREE(POLY_MAX_DEGREE),
            .NUM_BANKS(C * PB),
            .EVALUATION_ARCH(POLY_EVALUATION_ARCH),
            .CONTEXT_ID_WIDTH(8),
            .REQUEST_TAG_WIDTH(16),
            .COEFFICIENT_PROTECTION(COEFFICIENT_PROTECTION)
        ) u_poly (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_drain('0),
            .i_flush(clear_private),
            .i_error_clear('0),
            .i_request_valid(native_request && ctx.operation == SFT_POLYNOMIAL),
            .i_request_x(a[0+:INPUT_WIDTH]),
            .i_request_bank(PBI'(q.context_id * PB + ctx.bank)),
            .i_request_predicate(1'b1),
            .i_request_context_id(8'(q.context_id)),
            .i_request_tag(q.tag),
            .i_result_ready(native_consume),
            .i_program_valid(program_valid && program_poly),
            .i_program_command(program_command),
            .i_program_bank(PBI'(program_context * PB + program_bank)),
            .i_program_coefficient_index(DI'(program_index)),
            .i_program_coefficient_data(program_image[COEFFICIENT_BASE + program_index *
                POLY_COEFFICIENT_WIDTH+:POLY_COEFFICIENT_WIDTH]),
            .i_program_degree(DI'(programming_context.degree)),
            .i_program_x_min(programming_context.x_min[0+:INPUT_WIDTH]),
            .i_program_x_max(programming_context.x_max[0+:INPUT_WIDTH]),
            .i_program_range_policy(programming_context.range_error),
            .i_program_round_mode(programming_context.rounding),
            .i_program_result_shift(programming_context.shift[0+:6]),
            .i_program_polynomial_id(programming_context.polynomial_id),
            .i_program_quality_id(4'(programming_context.quality)),
            .i_program_response_ready(reset_known && program_phase == PROGRAM_RESPONSE),
            .o_result_valid(fu_valid[3]),
            .o_result_data(fu_data[3*OUTPUT_WIDTH+:OUTPUT_WIDTH]),
            .o_result_context_id(fu_context[3*8+:8]),
            .o_result_tag(fu_tag[3*16+:16]),
            .o_fatal_error(fu_fatal[3]),
            .o_request_ready(fu_ready[3]),
            .o_result_clipped_low(clip_low),
            .o_result_clipped_high(clip_high),
            .o_result_internal_saturated(internal_saturated),
            .o_result_output_saturated(output_saturated),
            .o_result_inexact(inexact),
            .o_result_error(result_error),
            .o_program_ready(poly_program_ready),
            .o_program_response_valid(poly_program_response),
            .o_bank_valid(poly_bank_valid),
            .o_program_response_error(poly_program_error)
        );
        assign fu_flags[3*16+:16] = {8'd0, clip_high, clip_low, 1'b0, inexact,
            output_saturated, 1'b0, internal_saturated, result_error};
    end else begin : g_no_polynomial
        assign fu_ready[3] = 1'b0;
        assign fu_valid[3] = 1'b0;
        assign fu_data[3*OUTPUT_WIDTH+:OUTPUT_WIDTH] = '0;
        assign fu_flags[3*16+:16] = '0;
        assign fu_context[3*8+:8] = '0;
        assign fu_tag[3*16+:16] = '0;
        assign fu_fatal[3] = 1'b0;
        assign poly_bank_valid = '0;
        assign poly_program_ready = 1'b0;
        assign poly_program_response = 1'b0;
        assign poly_program_error = 1'b0;
    end

    if (FU_PROFILE >= 2) begin : g_normalization
        wire recip_overflow;
        wire recip_underflow;
        wire recip_saturated;
        wire recip_rounded;
        wire recip_approximate;
        wire recip_error;
        wire recip_zero;

        reciprocal_unit #(
            .INPUT_WIDTH(INPUT_WIDTH),
            .INPUT_FRACTION_WIDTH(INPUT_FRAC_BITS),
            .INTERNAL_WIDTH(RECIP_INTERNAL_WIDTH),
            .INTERNAL_FRACTION_WIDTH(RECIP_INTERNAL_FRAC_BITS),
            .OUTPUT_WIDTH(OUTPUT_WIDTH),
            .OUTPUT_FRACTION_WIDTH(OUTPUT_FRAC_BITS),
            .MAX_ITERATIONS(RECIP_MAX_ITERATIONS),
            .CONTEXT_ID_WIDTH(8),
            .REQUEST_TAG_WIDTH(16),
            .SEED_PROTECTION(TABLE_PROTECTION),
            .SEED_ADDRESS_WIDTH(RECIP_SEED_ADDRESS_WIDTH)
        ) u_recip (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_drain('0),
            .i_flush(clear_private),
            .i_error_clear('0),
            .i_request_valid(native_request && ctx.operation == 4),
            .i_request_operand(a[0+:INPUT_WIDTH]),
            .i_request_signed(ctx.signed_data),
            .i_request_iterations(IT'(ctx.iterations)),
            .i_request_round_mode(ctx.rounding),
            .i_request_predicate(1'b1),
            .i_request_context_id(8'(q.context_id)),
            .i_request_tag(q.tag),
            .i_result_ready(native_consume),
            .o_request_ready(fu_ready[4]),
            .o_result_valid(fu_valid[4]),
            .o_result_data(fu_data[4*OUTPUT_WIDTH+:OUTPUT_WIDTH]),
            .o_result_context_id(fu_context[4*8+:8]),
            .o_result_tag(fu_tag[4*16+:16]),
            .o_fatal_error(fu_fatal[4]),
            .o_result_overflow(recip_overflow),
            .o_result_underflow(recip_underflow),
            .o_result_saturated(recip_saturated),
            .o_result_rounded(recip_rounded),
            .o_result_approximate(recip_approximate),
            .o_result_error(recip_error),
            .o_result_divide_by_zero(recip_zero)
        );

        assign fu_flags[4*16+:16] = {9'd0, recip_zero, recip_approximate,
            recip_rounded, recip_saturated, recip_underflow, recip_overflow, recip_error};
        wire rsqrt_overflow;
        wire rsqrt_underflow;
        wire rsqrt_saturated;
        wire rsqrt_rounded;
        wire rsqrt_approximate;
        wire rsqrt_error;
        wire rsqrt_zero;

        rsqrt_unit #(
            .INPUT_WIDTH(INPUT_WIDTH),
            .INPUT_FRACTION_WIDTH(INPUT_FRAC_BITS),
            .INTERNAL_WIDTH(RSQRT_INTERNAL_WIDTH),
            .INTERNAL_FRACTION_WIDTH(RSQRT_INTERNAL_FRAC_BITS),
            .OUTPUT_WIDTH(OUTPUT_WIDTH),
            .OUTPUT_FRACTION_WIDTH(OUTPUT_FRAC_BITS),
            .MAX_ITERATIONS(RSQRT_MAX_ITERATIONS),
            .CONTEXT_ID_WIDTH(8),
            .REQUEST_TAG_WIDTH(16),
            .SEED_PROTECTION(TABLE_PROTECTION),
            .SEED_MANTISSA_ADDRESS_WIDTH(RSQRT_SEED_ADDRESS_WIDTH)
        ) u_rsqrt (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_drain('0),
            .i_flush(clear_private),
            .i_error_clear('0),
            .i_request_valid(native_request && ctx.operation == 5),
            .i_request_operand(a[0+:INPUT_WIDTH]),
            .i_request_input_signed(ctx.signed_data),
            .i_request_output_signed(ctx.signed_data),
            .i_request_add_epsilon(ctx.epsilon != 0),
            .i_request_epsilon(ctx.epsilon[0+:INPUT_WIDTH]),
            .i_request_iterations(RT'(ctx.iterations)),
            .i_request_round_mode(ctx.rounding),
            .i_request_predicate(1'b1),
            .i_request_context_id(8'(q.context_id)),
            .i_request_tag(q.tag),
            .i_result_ready(native_consume),
            .o_request_ready(fu_ready[5]),
            .o_result_valid(fu_valid[5]),
            .o_result_data(fu_data[5*OUTPUT_WIDTH+:OUTPUT_WIDTH]),
            .o_result_context_id(fu_context[5*8+:8]),
            .o_result_tag(fu_tag[5*16+:16]),
            .o_fatal_error(fu_fatal[5]),
            .o_result_overflow(rsqrt_overflow),
            .o_result_underflow(rsqrt_underflow),
            .o_result_saturated(rsqrt_saturated),
            .o_result_rounded(rsqrt_rounded),
            .o_result_approximate(rsqrt_approximate),
            .o_result_error(rsqrt_error),
            .o_result_zero_input(rsqrt_zero)
        );

        assign fu_flags[5*16+:16] = {9'd0, rsqrt_zero, rsqrt_approximate,
            rsqrt_rounded, rsqrt_saturated, rsqrt_underflow, rsqrt_overflow, rsqrt_error};
    end else begin : g_no_normalization
        assign fu_ready[5:4] = '0;
        assign fu_valid[5:4] = '0;
        assign fu_fatal[5:4] = '0;
        assign fu_data[4*OUTPUT_WIDTH+:2*OUTPUT_WIDTH] = '0;
        assign fu_flags[4*16+:32] = '0;
        assign fu_context[4*8+:16] = '0;
        assign fu_tag[4*16+:32] = '0;
    end

    if (FU_PROFILE == 3) begin : g_exponential
        wire overflow;
        wire underflow;
        wire saturated;
        wire rounded;
        wire approximate;
        wire result_error;

        exp_unit #(
            .INPUT_WIDTH(INPUT_WIDTH),
            .INPUT_FRACTION_WIDTH(INPUT_FRAC_BITS),
            .RANGE_WIDTH(EXP_RANGE_WIDTH),
            .INTERNAL_WIDTH(INTERNAL_WIDTH),
            .INTERNAL_FRACTION_WIDTH(INTERNAL_FRAC_BITS),
            .OUTPUT_WIDTH(OUTPUT_WIDTH),
            .OUTPUT_FRACTION_WIDTH(OUTPUT_FRAC_BITS),
            .TABLE_ADDRESS_WIDTH(EXP_TABLE_ADDRESS_WIDTH),
            .PIPELINE_DEPTH(EXP_PIPELINE_DEPTH),
            .CONTEXT_ID_WIDTH(8),
            .REQUEST_TAG_WIDTH(16),
            .TABLE_PROTECTION(TABLE_PROTECTION)
        ) u_exp (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_drain('0),
            .i_flush(clear_private),
            .i_error_clear('0),
            .i_request_valid(native_request && ctx.operation == SFT_EXP),
            .i_request_base(ctx.base),
            .i_request_output_signed(ctx.signed_data),
            .i_request_interpolate(ctx.interpolate),
            .i_request_round_mode(ctx.rounding),
            .i_request_predicate(1'b1),
            .i_result_ready(native_consume),
            .i_request_operand(a[0+:INPUT_WIDTH]),
            .i_request_context_id(8'(q.context_id)),
            .i_request_tag(q.tag),
            .o_request_ready(fu_ready[6]),
            .o_result_valid(fu_valid[6]),
            .o_result_data(fu_data[6*OUTPUT_WIDTH+:OUTPUT_WIDTH]),
            .o_result_context_id(fu_context[6*8+:8]),
            .o_result_tag(fu_tag[6*16+:16]),
            .o_fatal_error(fu_fatal[6]),
            .o_result_overflow(overflow),
            .o_result_underflow(underflow),
            .o_result_saturated(saturated),
            .o_result_rounded(rounded),
            .o_result_approximate(approximate),
            .o_result_error(result_error)
        );

        assign fu_flags[6*16+:16] = {10'd0, approximate, rounded,
            saturated, underflow, overflow, result_error};
    end else begin : g_no_exponential
        assign fu_ready[6] = 1'b0;
        assign fu_valid[6] = 1'b0;
        assign fu_fatal[6] = 1'b0;
        assign fu_data[6*OUTPUT_WIDTH+:OUTPUT_WIDTH] = '0;
        assign fu_flags[6*16+:16] = '0;
        assign fu_context[6*8+:8] = '0;
        assign fu_tag[6*16+:16] = '0;
    end

    wire narrow_operation = ctx.operation == SFT_MULTIPLY ||
        ctx.operation == SFT_POLYNOMIAL || ctx.operation == SFT_RECIPROCAL ||
        ctx.operation == SFT_RSQRT || ctx.operation == SFT_EXP;
    wire [D-1:0] canonical_a = ctx.signed_data || ctx.operation == SFT_POLYNOMIAL ||
        ctx.operation == SFT_EXP ? D'($signed(a[0+:INPUT_WIDTH])) : D'(a[0+:INPUT_WIDTH]);
    wire [D-1:0] canonical_b = ctx.signed_data ? D'($signed(b[0+:INPUT_WIDTH])) :
        D'(b[0+:INPUT_WIDTH]);
    wire accumulator_state_error = dispatch && q.predicate && ctx.operation == SFT_ACCUMULATOR &&
        (ctx.opcode == 2 || ctx.opcode == 3) &&!source_valid[4];
    wire source_error = dispatch && q.predicate &&
        ((need_a &&!selected_valid[0]) || (need_b &&!selected_valid[1]));
    wire canonical_error = dispatch && q.predicate && REQUIRE_CANONICAL_FORMAT == 1 &&
        ((narrow_operation && a !== canonical_a) ||
        (ctx.operation == SFT_MULTIPLY && b !== canonical_b) ||
        (ctx.operation == SFT_LUT && a !== (ctx.signed_data ?
        D'($signed(a[0+:(1+LA+LF)])) : D'(a[0+:(1+LA+LF)]))));
    wire response_identity_error = native_consume && fu_valid[ctx.operation] &&
        (fu_context[ctx.operation*8+:8] !== 8'(q.context_id) ||
        fu_tag[ctx.operation*16+:16] !== q.tag);
    assign fatal_now = enabled && (program_bad || (|input_bad) || predicate_bad || request_bad ||
        (|fu_fatal) || (operands_present &&!operands_match) || accumulator_state_error ||
            source_error || canonical_error || response_identity_error ||
        (executing && (header_witness !== q.header_witness ||!legal(o_body_context_image,
            o_body_context_id))) ||
        (dispatch && q.predicate && ctx.operation == SFT_REDUCE &&!reduction_legal));
    assign fatal_code = canonical_error ? SFT_ERR_CANONICAL : source_error ? SFT_ERR_SOURCE :
        response_identity_error ? SFT_ERR_RESPONSE :
        dispatch && ctx.operation == SFT_REDUCE && reduction_count_limit ? SFT_ERR_COUNT :
        dispatch && ctx.operation == SFT_REDUCE &&!reduction_legal ? SFT_ERR_STATE :
        SFT_ERR_INTEGRITY;

    // A response is offered independently of ready. All selected shell
    // destinations must reserve together before any architectural state writes.
    wire retiring = executing && q.phase == ENGINE_RETIRE;
    wire emit_result = !q.suppress;
    wire destinations_ready = (o_body_data_out_ready & NO'(ctx.output_mask)) ==
        NO'(ctx.output_mask);
    assign commit = retiring && (!emit_result || destinations_ready) &&!fatal_now;
    logic [M-1:0] result_metadata;

    always @* begin
        result_metadata = q.metadata;
        result_metadata[CI+V] = !q.predicate;
        result_metadata[64+:8] = ctx.operation;
        result_metadata[72+:2] = ctx.quality;
        result_metadata[80+:32] = ctx.model;
        result_metadata[112+:16] = q.flags;
        result_metadata[128+:16] = q.count;
        result_metadata[144] = q.empty_result;
        result_metadata[152+:8] = ctx.result_format;
    end

    for (genvar p = 0; p < NO; p++) begin : g_output
        assign i_body_data_out_valid[p] = commit && emit_result && ctx.output_mask[p];
        assign i_body_data_out_payload[p*D+:D] = q.result;
        assign i_body_data_out_metadata[p*M+:M] = result_metadata;
    end

    assign i_body_predicate_out_valid = '0;
    assign i_body_predicate_out_payload = '0;
    assign i_body_predicate_out_metadata = '0;
    assign i_body_event_in_ready = '0;
    assign i_body_event_out_valid = '0;
    assign i_body_event_out_payload = '0;

    always @* begin
        n = q;
        next_rf_valid = q.rf_valid;

        if (clear_private) n = '0;
        else if (context_change) begin
            n.context_id = o_body_context_id;
            n.version = o_body_context_version;
            n.header_witness = header_witness;
            n.issued = '0;
            n.retired = '0;
            n.complete = 1'b0;
            n.advance_context = 1'b0;

            if (ctx.invalidate) begin
                n.rf_valid = '0;
                n.previous_valid = 1'b0;
            end
        end else if (enabled) begin
            if (o_body_start) begin
                n.started = 1'b1;
                n.complete = 1'b0;
                n.issued = '0;
                n.retired = '0;
            end

            if (issue) n.issued = q.issued + 1'b1;

            if (issue != commit) n.inflight = commit ? q.inflight - 1'b1 : q.inflight + 1'b1;

            if (request_pop && request_valid) begin
                n.inputs = request.inputs;
                n.metadata = request.metadata;
                n.predicate = request.predicate;
                n.reduction_phase = request.reduction_phase;
                n.tag = request.tag;
                n.phase = ENGINE_DISPATCH;
            end

            if (dispatch) begin
                n.flags = '0;
                n.count = '0;
                n.empty_result = 1'b0;
                n.suppress = 1'b0;

                if (!q.predicate) begin
                    n.result = '0;
                    n.flags[9] = 1'b1;
                    n.suppress = !ctx.false_token;
                    n.phase = ENGINE_RETIRE;
                end else if (ctx.operation >= SFT_LUT && ctx.operation <= SFT_EXP) begin
                    if (native_accept) n.phase = ENGINE_WAIT;
                end else begin
                    n.result = math_data;
                    n.flags = math_flags;
                    n.phase = ENGINE_RETIRE;

                    if (ctx.operation == SFT_REDUCE) begin
                        n.result = reduction_result;
                        n.count = reduction_count;
                        n.empty_result = reduction_empty;
                        n.flags[8] = reduction_empty;
                        n.flags[0] = reduction_empty && ctx.empty_policy == 1 &&
                            q.reduction_phase != REDUCE_CLEAR;
                        n.suppress = (q.reduction_phase == REDUCE_CLEAR ||
                            q.reduction_phase == REDUCE_BEGIN || q.reduction_phase == REDUCE_UPDATE)
                                ||
                            (reduction_empty && ctx.empty_policy == 2);
                    end else if (ctx.operation == SFT_ACCUMULATOR) begin
                        case (ctx.opcode)
                            0: n.result = '0;
                            1: n.result = a;
                            2: n.result = math_data;
                            3: n.result = accumulator_data;
                            default: n.result = '0;
                        endcase

                        n.flags = ctx.opcode == 2 ? math_flags : 16'd0;
                    end
                end
            end

            if (native_consume && fu_valid[ctx.operation]) begin
                n.result = ctx.signed_data || ctx.operation == SFT_POLYNOMIAL ?
                    D'($signed(fu_data[ctx.operation*OUTPUT_WIDTH+:OUTPUT_WIDTH])) :
                    D'(fu_data[ctx.operation*OUTPUT_WIDTH+:OUTPUT_WIDTH]);

                n.flags = fu_flags[ctx.operation*16+:16];

                if (ctx.operation == SFT_LUT && ctx.range_error && (lut_low || lut_high)) begin
                    n.result = '0;
                    n.flags = fu_flags[ctx.operation*16+:16] | 16'd1;
                end

                n.phase = ENGINE_RETIRE;
            end

            if (commit) begin
                n.retired = q.retired + 1'b1;
                n.phase = ENGINE_IDLE;

                if (q.predicate &&!q.flags[0]) begin
                    n.previous_valid = 1'b1;
                    n.previous = q.result;
                    n.previous_format = ctx.result_format;
                    n.previous_signed = ctx.signed_data;
                    n.previous_owner = i_owner;
                    n.previous_kernel = i_kernel;
                    n.previous_version = o_body_context_version;

                    if (ctx.write_rf) begin
                        next_rf_valid[ctx.rf_write] = 1'b1;
                        n.rf_valid = next_rf_valid;
                    end
                end

                if (q.retired + 1 >= ctx.steps) begin
                    n.complete = ctx.terminal;
                    n.advance_context = ctx.advance_context;
                end
            end

            if (o_advance_valid && i_advance_ready) n.advance_context = 1'b0;

            if (fatal_now) begin
                n.fatal = 1'b1;
                n.error_code = fatal_code;
            end
        end

        // START is a shell wakeup event and may arrive while the body was gated.
        if (o_body_start &&!clear_private) begin
            n.started = 1'b1;
            n.complete = 1'b0;
            n.issued = '0;
            n.retired = '0;
        end
    end

    wire all_inputs_empty = input_counts == 0 && predicate_count == 0;
    wire transport_empty = q.inflight == 0 && q.phase == ENGINE_IDLE && request_count == 0;
    assign i_body_busy = !transport_empty ||!all_inputs_empty;
    assign i_body_idle = transport_empty && all_inputs_empty;
    assign i_body_safe_point = transport_empty;
    assign i_body_drain_done = transport_empty && all_inputs_empty;
    assign i_body_completed = q.complete &&!o_body_start &&!context_change && transport_empty &&
        all_inputs_empty
        &&!fatal_latch;
    assign o_advance_valid = q.advance_context &&!context_change && transport_empty &&
        all_inputs_empty &&
        !fatal_latch && enabled;
    assign o_advance_context = CI'(ctx.next_context);
    assign i_body_error = q.fatal || fatal_latch || control_bad;
    assign i_body_fatal_error = i_body_error;
    assign i_body_error_code = q.error_code != 0 ? q.error_code : 8'(SFT_ERR_INTEGRITY);
    assign i_body_wakeup_required = i_body_busy || o_body_validate_valid;

    // Stall reporting is independent of the shell's clock-enable decision.
    // Reserved internal work keeps activity asserted until it can retire.
    assign i_body_stall_reasons = {6'd0,
        q.phase == ENGINE_RETIRE &&!destinations_ready,
        q.started &&!q.complete &&!q.advance_context && q.issued < ctx.steps && transport_empty &&
            all_inputs_empty &&!operands_present};

    logic [31:0] counter_events;
    logic [32*8-1:0] counter_increments;
    logic [32*5-1:0] counter_select;

    always @* begin
        counter_events = '0;
        counter_increments = '0;
        counter_select = '0;
        counter_events[0] = issue;
        counter_events[1] = commit;

        for (int f = 0; f < 10; f++) counter_events[f+2] =
            dispatch && q.predicate && ctx.operation == f;

        counter_events[12] = retiring &&!destinations_ready;
        counter_events[13] = q.inflight >= MAX_INFLIGHT;
        counter_events[14] = issue &&!offered.predicate;
        counter_events[15] = write_rf;
        counter_events[16] = write_acc;
        counter_events[17] = red_update;
        counter_events[18] = program_valid && program_ready;
        counter_events[19] = o_advance_valid && i_advance_ready;
        counter_events[20] = control_corrected || program_corrected;
        counter_events[21] = fatal_now;
        counter_events[22] = i_body_idle;
        counter_events[23] = i_clock_enable;
        counter_events[24] = commit && q.flags[0];

        for (int k = 0; k < 32; k++) begin
            counter_increments[k*8+:8] = 8'd1;
            counter_select[k*5+:5] = 5'(k);
        end
    end

    performance_counters #(
        .COUNTER_WIDTH(32),
        .NUM_COUNTERS(32),
        .NUM_EVENTS(32),
        .INCREMENT_WIDTH(8),
        .HAS_SNAPSHOT(0),
        .HAS_THRESHOLD(0)
    ) u_counters (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_global_enable(reset_known && i_monitor_enable && ctx.monitor),
        .i_freeze(1'b0),
        .i_counter_enable('1),
        .i_clear({32{clear_private}}),
        .i_event_select(counter_select),
        .i_event_valid(counter_events),
        .i_event_increment(counter_increments),
        .i_threshold_enable('0),
        .i_threshold_value('0),
        .i_snapshot(1'b0),
        .i_read_enable(1'b1),
        .i_read_snapshot(1'b0),
        .i_read_index(i_counter_index),
        .o_read_data(o_counter_data),
        .o_read_valid(),
        .o_read_overflow(),
        .o_counter_overflow(),
        .o_threshold_event(),
        .o_config_error(),
        .o_snapshot_valid()
    );

    // Read-only observations used by the Python ownership/retirement checker.
    wire [D-1:0] result = q.result;
    wire [15:0] result_flags = q.flags;
    wire [15:0] result_count = q.count;
    wire result_empty = q.empty_result;
    wire result_suppress = q.suppress;
    wire [2:0] engine_phase = q.phase;
    wire [15:0] issued_tag = q.issued;
    wire [15:0] retired_tag = q.tag;
endmodule
`default_nettype wire
