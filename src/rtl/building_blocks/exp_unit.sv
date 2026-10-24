`timescale 1ns / 1ps

// Five elastic arithmetic boundaries followed by a registered result queue.
// Accept at edge t -> result valid after edge t + PIPELINE_DEPTH when unstalled.
module exp_unit #(
    parameter INPUT_WIDTH = 16,
    parameter INPUT_FRACTION_WIDTH = 8,
    parameter RANGE_WIDTH = 40,
    parameter RANGE_FRACTION_WIDTH = 20,
    parameter LOG2E_FRACTION_WIDTH = 24,
    parameter INTERNAL_WIDTH = 24,
    parameter INTERNAL_FRACTION_WIDTH = 20,
    parameter OUTPUT_WIDTH = 16,
    parameter OUTPUT_FRACTION_WIDTH = 12,
    parameter TABLE_ADDRESS_WIDTH = 6,
    parameter SUPPORT_EXP_E = 1,
    parameter SUPPORT_EXP2 = 1,
    parameter SUPPORT_INTERPOLATION = 1,
    parameter PIPELINE_DEPTH = 5,
    parameter OUTPUT_QUEUE_DEPTH = 2,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter REQUEST_TAG_WIDTH = 8,
    parameter TABLE_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((INPUT_WIDTH >= 1) === 1'b1) && ( ^ INPUT_WIDTH !== 1'bx) &&
        ((INPUT_FRACTION_WIDTH >= 1) === 1'b1) && ( ^ INPUT_FRACTION_WIDTH !== 1'bx) &&
        ((RANGE_WIDTH >= 1) === 1'b1) && ( ^ RANGE_WIDTH !== 1'bx) &&
        ((RANGE_FRACTION_WIDTH >= 1) === 1'b1) && ( ^ RANGE_FRACTION_WIDTH !== 1'bx) &&
        ((LOG2E_FRACTION_WIDTH >= 1) === 1'b1) && ( ^ LOG2E_FRACTION_WIDTH !== 1'bx) &&
        ((INTERNAL_WIDTH >= 1) === 1'b1) && ( ^ INTERNAL_WIDTH !== 1'bx) &&
        ((INTERNAL_FRACTION_WIDTH >= 1) === 1'b1) && ( ^ INTERNAL_FRACTION_WIDTH !== 1'bx) &&
        ((OUTPUT_WIDTH >= 1) === 1'b1) && ( ^ OUTPUT_WIDTH !== 1'bx) &&
        ((OUTPUT_FRACTION_WIDTH >= 1) === 1'b1) && ( ^ OUTPUT_FRACTION_WIDTH !== 1'bx) &&
        ((TABLE_ADDRESS_WIDTH >= 1) === 1'b1) && ( ^ TABLE_ADDRESS_WIDTH !== 1'bx) &&
        ((PIPELINE_DEPTH >= 1) === 1'b1) && ( ^ PIPELINE_DEPTH !== 1'bx) &&
        ((OUTPUT_QUEUE_DEPTH >= 1) === 1'b1) && ( ^ OUTPUT_QUEUE_DEPTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ^ CONTEXT_ID_WIDTH !== 1'bx) &&
        ((REQUEST_TAG_WIDTH >= 1) === 1'b1) && ( ^ REQUEST_TAG_WIDTH !== 1'bx) &&
        ((SUPPORT_EXP_E === 0) || (SUPPORT_EXP_E === 1)) &&
        ((SUPPORT_EXP2 === 0) || (SUPPORT_EXP2 === 1)) &&
        ((SUPPORT_INTERPOLATION === 0) || (SUPPORT_INTERPOLATION === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((TABLE_PROTECTION === 0) || (TABLE_PROTECTION === 1) ||
            (TABLE_PROTECTION === 2)) &&
        ((SUPPORT_EXP_E == 1 || SUPPORT_EXP2 == 1) === 1'b1) &&
        ((INPUT_FRACTION_WIDTH < INPUT_WIDTH) === 1'b1) &&
        ((RANGE_FRACTION_WIDTH < RANGE_WIDTH) === 1'b1) &&
        ((OUTPUT_FRACTION_WIDTH < OUTPUT_WIDTH) === 1'b1) &&
        ((64'(INTERNAL_WIDTH) >= 64'(INTERNAL_FRACTION_WIDTH) + 2) === 1'b1) &&
        ((TABLE_ADDRESS_WIDTH < RANGE_FRACTION_WIDTH) === 1'b1) &&
        ((TABLE_ADDRESS_WIDTH <= exp_unit_tables_pkg::MAX_ADDRESS) === 1'b1) &&
        ((INTERNAL_FRACTION_WIDTH <= exp_unit_tables_pkg::MAX_FRACTION) === 1'b1) &&
        ((LOG2E_FRACTION_WIDTH <= exp_unit_tables_pkg::MAX_FRACTION) === 1'b1) &&
        ((INTERNAL_WIDTH <= 256) === 1'b1) &&
        ((PIPELINE_DEPTH >= 5) === 1'b1) &&
        (($signed(64'(RANGE_WIDTH)) >= $signed(64'(INPUT_WIDTH)) +
            $signed(64'(RANGE_FRACTION_WIDTH)) - $signed(64'(INPUT_FRACTION_WIDTH)) +
            (SUPPORT_EXP_E == 1 ? 1 : 0)) === 1'b1) &&
        ((64'(INPUT_WIDTH) + 64'(LOG2E_FRACTION_WIDTH) +
            64'(RANGE_FRACTION_WIDTH) + 3 < 64'd2147483647) === 1'b1) &&
        (((64'(RANGE_WIDTH) + 64'(OUTPUT_WIDTH) + 2 * 64'(INTERNAL_WIDTH) +
            64'(CONTEXT_ID_WIDTH) + 64'(REQUEST_TAG_WIDTH) + 64'd64) *
            (64'(PIPELINE_DEPTH) + 64'(OUTPUT_QUEUE_DEPTH)) < 64'd2147483647) === 1'b1) &&
        ((INPUT_WIDTH < 2147483647) === 1'b1) &&
        ((INPUT_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ((RANGE_WIDTH < 2147483647) === 1'b1) &&
        ((RANGE_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ((LOG2E_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ((INTERNAL_WIDTH < 2147483647) === 1'b1) &&
        ((INTERNAL_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ((OUTPUT_WIDTH < 2147483647) === 1'b1) &&
        ((OUTPUT_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ((TABLE_ADDRESS_WIDTH < 2147483647) === 1'b1) &&
        ((PIPELINE_DEPTH < 2147483647) === 1'b1) &&
        ((OUTPUT_QUEUE_DEPTH < 2147483647) === 1'b1) &&
        ((CONTEXT_ID_WIDTH < 2147483647) === 1'b1) &&
        ((REQUEST_TAG_WIDTH < 2147483647) === 1'b1),
    localparam int IW = PARAMETERS_VALID ? INPUT_WIDTH : 1,
    localparam int XF = PARAMETERS_VALID ? INPUT_FRACTION_WIDTH : 1,
    localparam int RW = PARAMETERS_VALID ? RANGE_WIDTH : 1,
    localparam int RF = PARAMETERS_VALID ? RANGE_FRACTION_WIDTH : 1,
    localparam int LF = PARAMETERS_VALID ? LOG2E_FRACTION_WIDTH : 1,
    localparam int I = PARAMETERS_VALID ? INTERNAL_WIDTH : 1,
    localparam int F = PARAMETERS_VALID ? INTERNAL_FRACTION_WIDTH : 1,
    localparam int OW = PARAMETERS_VALID ? OUTPUT_WIDTH : 1,
    localparam int OF = PARAMETERS_VALID ? OUTPUT_FRACTION_WIDTH : 1,
    localparam int TA = PARAMETERS_VALID ? TABLE_ADDRESS_WIDTH : 1,
    localparam int L = PARAMETERS_VALID ? PIPELINE_DEPTH : 1,
    localparam int QD = PARAMETERS_VALID ? OUTPUT_QUEUE_DEPTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int T = PARAMETERS_VALID ? REQUEST_TAG_WIDTH : 1,
    localparam int EW = RW - RF > 0 ? RW - RF : 1,
    localparam int REM = RF - TA > 0 ? RF - TA : 1,
    localparam int QW = $clog2(QD + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_request_valid,
    input logic i_request_base,
    input logic i_request_output_signed,
    input logic i_request_interpolate,
    input logic i_request_round_mode,
    input logic i_request_predicate,
    input logic i_result_ready,
    input logic [IW-1:0] i_request_operand,
    input logic [C-1:0] i_request_context_id,
    input logic [T-1:0] i_request_tag,
    output logic o_request_ready,
    output logic o_result_valid,
    output logic o_result_base,
    output logic o_result_output_signed,
    output logic o_result_interpolated,
    output logic o_result_overflow,
    output logic o_result_underflow,
    output logic o_result_saturated,
    output logic o_result_rounded,
    output logic o_result_approximate,
    output logic o_result_predicated,
    output logic o_result_error,
    output logic o_busy,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic o_fatal_error,
    output logic o_event_request_accept,
    output logic o_event_result_complete,
    output logic o_event_request_stall,
    output logic o_event_result_stall,
    output logic o_event_base_e,
    output logic o_event_base_2,
    output logic o_event_table_lookup,
    output logic o_event_interpolation,
    output logic o_event_overflow,
    output logic o_event_underflow,
    output logic o_event_table_corrected,
    output logic o_event_table_uncorrectable,
    output logic [OW-1:0] o_result_data,
    output logic [EW-1:0] o_result_reduced_exponent,
    output logic [31:0] o_result_quality_id,
    output logic [31:0] o_table_image_id,
    output logic [31:0] o_table_checksum,
    output logic [31:0] o_log2e_constant_id,
    output logic [31:0] o_log2e_checksum,
    output logic [C-1:0] o_result_context_id,
    output logic [T-1:0] o_result_tag,
    output logic [3:0] o_result_error_code,
    output logic [3:0] o_error_code,
    output logic [QW-1:0] o_output_queue_occupancy
);
    import exp_unit_pkg::*;
    import exp_unit_tables_pkg::*;

    function automatic logic [31:0] format_id;
            logic [319:0] format_bits;
            logic [31:0] crc;

            format_bits = {32'(IW), 32'(XF), 32'(RW), 32'(RF), 32'(LF),
                32'(I), 32'(F), 32'(OW), 32'(OF), 32'(TA)};
            crc = '1;

            for (int byte_index = 0; byte_index < 40; byte_index++) begin
                crc = crc ^ {24'b0, format_bits[byte_index*8+:8]};

                for (int bit_index = 0; bit_index < 8; bit_index++)
                    crc = crc[0] ? (crc >> 1) ^ 32'hedb88320 : crc >> 1;
            end

            return (~ crc) & 32'hfffffff0;
    endfunction

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        exp_unit_parameters_must_be_valid invalid_parameters ();
    end else begin : g_unit
        localparam int CONV_WIDTH = IW + LF + RF + 3 > RW ? IW + LF + RF + 3 : RW;
        localparam int CONV_SHIFT_WIDTH = $clog2(CONV_WIDTH + 1);
        localparam int MULTIPLY_WIDTH = IW > LF + 2 ? IW : LF + 2;
        localparam int PRODUCT_WIDTH = IW + LF + 2;
        localparam int SCALE_WIDTH = I + OW + 1;
        localparam int SHIFT_WIDTH = EW + 2 > $clog2(F + OF + 1) + 2 ?
            EW + 2 : $clog2(F + OF + 1) + 2;
        localparam int RIGHT_SHIFT_LIMIT = I + 1;
        localparam int D2 = EW + REM + 2 * I;
        localparam int D3 = EW + I;
        localparam int D4 = EW + OW + 3;
        localparam int MAX_DATA = RW > D2 ? (RW > D4 ? RW : D4) : (D2 > D4 ? D2 : D4);
        localparam int COUNT_WIDTH = $clog2(L + QD + 1);
        localparam logic [LF+1:0] LOG2E = (LF + 2)'(round_master(LOG2E_MASTER, LF));
        localparam logic [31:0] IMAGE_CRC = table_crc(TA, F, I);
        localparam logic [31:0] CONSTANT_CRC = constant_crc(LF);
        localparam logic [31:0] IMAGE_ID = IMAGE_CRC ^ 32'h45585001;
        localparam logic [31:0] CONSTANT_ID = CONSTANT_CRC ^ 32'h4c324501;

        // Parameterized metadata remains local. Its active bit is first so the
        // common stage wrapper can clock-enable arithmetic without decoding it.
        typedef struct packed {
            logic active;
            logic base;
            logic output_signed;
            logic interpolate;
            logic round_mode;
            logic predicated;
            logic error;
            logic [3:0] error_code;
            logic rounded;
            logic [C-1:0] context_id;
            logic [T-1:0] tag;
        } control_t;

        localparam int CONTROL = $bits(control_t);
        localparam int RESPONSE = CONTROL + D4;
        localparam logic [31:0] QUALITY_ID = format_id();

        wire state_rstb = i_rstb !== 1'b0;
        wire controls_known = ( ^ {i_rstb, i_drain, i_flush, i_error_clear,
            i_request_valid, i_result_ready} !== 1'bx);
        wire fields_known = ( ^ {i_request_operand, i_request_base, i_request_output_signed,
            i_request_interpolate, i_request_round_mode, i_request_predicate,
            i_request_context_id, i_request_tag} !== 1'bx);
        wire unsupported_base = i_request_base == EXP_BASE_E ?
            SUPPORT_EXP_E == 0 : SUPPORT_EXP2 == 0;
        wire unsupported_interpolation = i_request_interpolate && SUPPORT_INTERPOLATION == 0;
        wire legal = fields_known &&!unsupported_base &&!unsupported_interpolation;
        wire permit = i_rstb === 1'b1 && controls_known && i_flush === 1'b0 &&!o_fatal_error;
        wire flush = i_rstb === 1'b1 && i_flush === 1'b1;
        wire active_input = permit && i_request_valid === 1'b1 && legal && i_request_predicate;
        wire [31:0] image_identity = IMAGE_ID;
        wire [31:0] constant_identity = CONSTANT_ID;
        wire identity_fault = image_identity !== IMAGE_ID || constant_identity !== CONSTANT_ID;
        wire live_fault;
        wire run = permit &&!live_fault;
        wire accepted = i_request_valid === 1'b1 && o_request_ready;
        wire result_pop = o_result_valid && i_result_ready;
        wire [L:0] valid;
        wire [L-1:0] ready;
        wire [L-1:0] stage_corrupt;
        wire [CONTROL-1:0] control_bits[L+1];
        wire [MAX_DATA-1:0] stage_data[L+1];
        logic [CONTROL-1:0] next_control[L];
        logic [MAX_DATA-1:0] next_data[L];
        wire queue_ready;
        wire queue_valid;
        wire queue_corrupt;
        wire [RESPONSE-1:0] queue_output;
        wire result_create = run && valid[L] && queue_ready;
        wire [COUNT_WIDTH-1:0] in_flight;
        logic [COUNT_WIDTH-1:0] observed_occupancy;
        wire ownership_fault = (observed_occupancy !== in_flight) || (|stage_corrupt) ||
            queue_corrupt;
        assign valid[0] = permit &&!i_drain && i_request_valid === 1'b1 && fields_known;
        assign control_bits[0] = '0;
        assign stage_data[0] = '0;
        assign o_request_ready = run &&!i_drain && fields_known && ready[0];
        assign o_table_image_id = image_identity;
        assign o_table_checksum = IMAGE_CRC;
        assign o_log2e_constant_id = constant_identity;
        assign o_log2e_checksum = CONSTANT_CRC;

        // Base-e multiplication is completely absent in base-2-only profiles.
        wire signed [PRODUCT_WIDTH-1:0] product_e;

        if (SUPPORT_EXP_E == 1) begin : g_base_e
            wire enabled = active_input && i_request_base == EXP_BASE_E;
            wire [2*MULTIPLY_WIDTH-1:0] full_product;

            // Preserve the input sign and the generated constant's positive
            // sign before adapting unequal widths to the common multiplier.
            multiplier #(.OPERAND_WIDTH(MULTIPLY_WIDTH), .LATENCY(0)) u_multiply (
                .i_clk(1'b0),
                .i_rstb(1'b1),
                .i_clock_enable(1'b1),
                .i_valid(enabled),
                .i_operand_a(MULTIPLY_WIDTH'($signed(i_request_operand))),
                .i_operand_b(MULTIPLY_WIDTH'(LOG2E)),
                .i_signed_a(1'b1),
                .i_signed_b(1'b1),
                .o_product(full_product),
                .o_valid(),
                .o_product_signed(),
                .o_zero(),
                .o_negative()
            );
            assign product_e = $signed(full_product[PRODUCT_WIDTH-1:0]);
        end else begin : g_no_base_e
            assign product_e = '0;
        end

        wire [IW-1:0] isolated_2 = active_input && i_request_base == EXP_BASE_2 ?
            i_request_operand : '0;
        wire signed [CONV_WIDTH-1:0] conversion_source = i_request_base == EXP_BASE_E ?
            CONV_WIDTH'($signed(product_e)) : CONV_WIDTH'($signed(isolated_2));
        wire signed [31:0] conversion_shift = i_request_base == EXP_BASE_E ?
            RF - XF - LF : RF - XF;
        wire [CONV_SHIFT_WIDTH-1:0] conversion_right_shift = conversion_shift < 0 ?
            CONV_SHIFT_WIDTH'(-conversion_shift) : '0;
        wire signed [CONV_WIDTH-1:0] conversion_rounded;
        wire conversion_lost;

        // Magnitude rounding restores the sign, so negative conversion truncates
        // toward zero. Positive shifts are exact and need no rounding boundary.
        polynomial_unit_round #(
            .WIDTH(CONV_WIDTH),
            .SHIFT_WIDTH(CONV_SHIFT_WIDTH)
        ) u_convert_round (
            .i_value(conversion_source),
            .i_shift(conversion_right_shift),
            .i_nearest(i_request_round_mode),
            .o_value(conversion_rounded),
            .o_inexact(conversion_lost)
        );

        wire [CONV_WIDTH:0] converted = {conversion_lost,
            conversion_shift >= 0 ? conversion_source << conversion_shift : conversion_rounded};
        wire signed [CONV_WIDTH-1:0] coordinate = $signed(converted[CONV_WIDTH-1:0]);
        wire [CONV_WIDTH-1:0] reconstructed_coordinate =
            CONV_WIDTH'($signed(coordinate[RW-1:0]));
        wire conversion_fault = active_input && (coordinate !== reconstructed_coordinate);

        control_t input_control;
        always_comb begin
            input_control = '0;
            input_control.active = legal && i_request_predicate;
            input_control.base = i_request_base;
            input_control.output_signed = i_request_output_signed;
            input_control.interpolate = i_request_interpolate;
            input_control.round_mode = i_request_round_mode;
            input_control.context_id = i_request_context_id;
            input_control.tag = i_request_tag;
            input_control.predicated = legal &&!i_request_predicate;
            input_control.error = !legal;
            input_control.error_code = unsupported_base ? EXP_ERR_BASE :
                unsupported_interpolation ? EXP_ERR_INTERPOLATION : EXP_ERR_NONE;
            input_control.rounded = active_input && converted[CONV_WIDTH];
            next_data[0] = MAX_DATA'(coordinate[RW-1:0]);
        end

        always_comb next_control[0] = input_control;

        // S1: two's-complement bit partition is floor, including negative fractions.
        wire signed [RW-1:0] z1 = $signed(stage_data[1][RW-1:0]);
        always_comb begin
            next_control[1] = control_bits[1];
            next_data[1] = MAX_DATA'({z1[RW-1:RF], z1[RF-1:0]});
        end

        // S2: read both independently protected endpoints only when required.
        control_t table_control;
        wire [CONTROL-1:0] unused_table_control_fields = table_control;
        assign table_control = control_bits[2];
        wire [RW-1:0] z2 = stage_data[2][RW-1:0];
        wire [I-1:0] table_lower;
        wire [I-1:0] table_upper;
        wire table_corrected;
        wire table_bad;
        wire table_enable = permit && valid[2] && table_control.active;

        exp_unit_rom #(.WIDTH(I), .FRACTION(F), .ADDRESS(TA),
            .PROTECTION(TABLE_PROTECTION)) u_table (
            .i_enable(table_enable),
            .i_upper_enable(SUPPORT_INTERPOLATION == 1 && table_control.interpolate),
            .i_address(z2[RF-1:REM]),
            .o_lower(table_lower),
            .o_upper(table_upper),
            .o_corrected(table_corrected),
            .o_uncorrectable(table_bad)
        );

        always_comb begin
            next_control[2] = control_bits[2];
            next_data[2] = MAX_DATA'({z2[RW-1:RF], z2[REM-1:0], table_lower, table_upper});
        end

        // S3: full unsigned difference/product, followed by request rounding.
        control_t interpolate_control;
        wire [CONTROL-1:0] unused_interpolate_control_fields = interpolate_control;
        assign interpolate_control = control_bits[3];
        wire [D2-1:0] interpolation_data = stage_data[3][D2-1:0];
        wire [EW-1:0] k3;
        wire [REM-1:0] remainder3;
        wire [I-1:0] lower3;
        wire [I-1:0] upper3;
        assign {k3, remainder3, lower3, upper3} = interpolation_data;
        wire [I-1:0] mantissa;
        wire interpolation_lost;
        wire interpolation_fault;

        if (SUPPORT_INTERPOLATION == 1) begin : g_interpolation
            wire enabled = permit && valid[3] && interpolate_control.active &&
                interpolate_control.interpolate;

            exp_unit_interpolate #(.WIDTH(I), .REMAINDER_WIDTH(REM)) u_interpolate (
                .i_enable(enabled),
                .i_nearest(interpolate_control.round_mode),
                .i_lower(lower3),
                .i_upper(upper3),
                .i_remainder(remainder3),
                .o_mantissa(mantissa),
                .o_inexact(interpolation_lost),
                .o_bad(interpolation_fault)
            );
        end else begin : g_no_interpolation
            assign mantissa = lower3;
            assign interpolation_lost = 1'b0;
            assign interpolation_fault = 1'b0;
            wire [I+REM-1:0] unused_upper_remainder = {upper3, remainder3};
        end

        control_t interpolated_control;
        always_comb begin
            interpolated_control = control_bits[3];
            interpolated_control.rounded = interpolate_control.rounded || interpolation_lost;
            next_data[3] = MAX_DATA'({k3, mantissa});
        end

        always_comb next_control[3] = interpolated_control;

        // S4: compare the unrounded rational magnitude to the output maximum.
        // Explicit overshift cases prevent conversion of a huge exponent to int.
        control_t scale_control;
        wire [CONTROL-1:0] unused_scale_control_fields = scale_control;
        assign scale_control = control_bits[4];
        wire [EW-1:0] k4 = stage_data[4][D3-1:I];
        wire [I-1:0] m4 = stage_data[4][I-1:0];
        wire signed [SHIFT_WIDTH-1:0] shift = SHIFT_WIDTH'($signed(k4)) +
            SHIFT_WIDTH'(OF) - SHIFT_WIDTH'(F);
        wire [OW-1:0] maximum = scale_control.output_signed ?
            {1'b0, {(OW - 1){1'b1}}} : {OW{1'b1}};
        logic [SCALE_WIDTH-1:0] scaled;
        logic [SCALE_WIDTH-1:0] discarded_scale;
        logic [SCALE_WIDTH-1:0] scale_half;
        logic scale_overflow;
        logic scale_lost;
        logic [OW-1:0] result;
        integer shift_count;
        control_t scaled_control;

        always_comb begin
            scaled = '0;
            discarded_scale = '0;
            scale_half = '0;
            scale_overflow = 1'b0;
            scale_lost = 1'b0;
            shift_count = 0;

            if (valid[4] && scale_control.active) begin
                if (shift >= 0) begin
                    if (shift >= SHIFT_WIDTH'(OW)) scale_overflow = 1'b1;
                    else begin
                        scaled = SCALE_WIDTH'(m4) << int'(shift);
                        scale_overflow = scaled > SCALE_WIDTH'(maximum);
                    end
                end else if (shift <= -SHIFT_WIDTH'(RIGHT_SHIFT_LIMIT)) scale_lost = |m4;
                else begin
                    shift_count = -int'(shift);
                    scaled = SCALE_WIDTH'(m4) >> shift_count;
                    scale_half = {{(SCALE_WIDTH - 1){1'b0}}, 1'b1} << (shift_count - 1);
                    discarded_scale = SCALE_WIDTH'(m4) & ((scale_half << 1) - 1'b1);
                    scale_lost = |discarded_scale;
                    scale_overflow = SCALE_WIDTH'(m4) >
                        (SCALE_WIDTH'(maximum) << shift_count);
                    if (scale_control.round_mode && (discarded_scale > scale_half ||
                        (discarded_scale == scale_half && scaled[0]))) scaled = scaled + 1'b1;
                end
            end

            result = scale_overflow ? maximum : scaled[OW-1:0];
            scaled_control = control_bits[4];
            scaled_control.rounded = scale_control.rounded || scale_lost;
            next_data[4] = MAX_DATA'({k4, result, scale_overflow,
                scale_control.active && result == '0, scale_overflow});
        end

        always_comb next_control[4] = scaled_control;

        for (genvar s = 0; s < L; s++) begin : g_stage
            localparam int DATA = s < 2 ? RW : s == 2 ? D2 : s == 3 ? D3 : D4;
            wire [DATA-1:0] captured_data;
            wire downstream_ready;

            if (s == L - 1) begin : g_last
                assign downstream_ready = queue_ready;
            end else begin : g_forward
                assign downstream_ready = ready[s+1];
            end

            if (s >= 5) begin : g_extra
                always_comb begin
                    next_control[s] = control_bits[s];
                    next_data[s] = stage_data[s];
                end
            end

            exp_unit_stage #(
                .CONTROL(CONTROL),
                .DATA(DATA),
                .PROTECTED(TABLE_PROTECTION != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_slice (
                .i_clk(i_clk),
                .i_rstb(state_rstb),
                .i_flush(flush),
                .i_enable(run),
                .i_valid(valid[s]),
                .o_ready(ready[s]),
                .i_control(next_control[s]),
                .i_data(next_data[s][DATA-1:0]),
                .o_valid(valid[s+1]),
                .i_ready(downstream_ready),
                .o_control(control_bits[s+1]),
                .o_data(captured_data),
                .o_corrupt(stage_corrupt[s])
            );

            assign stage_data[s+1] = MAX_DATA'(captured_data);
        end

        wire [QD-1:0] unused_occupied;
        wire [QD*RESPONSE-1:0] unused_contents;

        event_barrier_queue #(
            .WIDTH(RESPONSE),
            .DEPTH(QD),
            .PROTECTED(TABLE_PROTECTION != 0),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_results (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_flush(flush),
            .i_valid(run && valid[L]),
            .o_ready(queue_ready),
            .i_data({control_bits[L], stage_data[L][D4-1:0]}),
            .o_valid(queue_valid),
            .i_ready(run && i_result_ready),
            .o_data(queue_output),
            .o_occupancy(o_output_queue_occupancy),
            .o_corrupt(queue_corrupt),
            .o_occupied(unused_occupied),
            .o_contents(unused_contents)
        );

        control_t result_control;
        assign result_control = queue_output[RESPONSE-1:D4];
        assign o_result_valid = run && queue_valid;
        assign {o_result_reduced_exponent, o_result_data, o_result_overflow,
            o_result_underflow, o_result_saturated} = o_result_valid ? queue_output[D4-1:0] : '0;
        assign o_result_base = o_result_valid && result_control.base;
        assign o_result_output_signed = o_result_valid && result_control.output_signed;
        assign o_result_interpolated = o_result_valid && result_control.active &&
            result_control.interpolate;
        assign o_result_rounded = o_result_valid && result_control.rounded;
        assign o_result_approximate = o_result_valid && result_control.active;
        assign o_result_predicated = o_result_valid && result_control.predicated;
        assign o_result_error = o_result_valid && result_control.error;
        assign o_result_error_code = o_result_valid ? result_control.error_code : '0;
        assign o_result_context_id = o_result_valid ? result_control.context_id : '0;
        assign o_result_tag = o_result_valid ? result_control.tag : '0;
        assign o_result_quality_id = o_result_valid && result_control.active ? QUALITY_ID |
            {28'b0, result_control.base, result_control.interpolate,
                result_control.round_mode, result_control.output_signed} : '0;

        always_comb begin
            observed_occupancy = COUNT_WIDTH'(o_output_queue_occupancy);

            for (int s = 1; s <= L; s++)
                observed_occupancy = observed_occupancy + COUNT_WIDTH'(valid[s]);
        end

        wire update_count = flush || (accepted != result_pop);
        wire [COUNT_WIDTH-1:0] next_count = flush ? '0 :
            accepted ? in_flight + 1'b1 : in_flight - 1'b1;
        wire unused_overflow;
        wire unused_underflow;
        wire unused_terminal;

        counter #(.WIDTH(COUNT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_in_flight (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(1'b0),
            .i_clear(1'b0),
            .i_load(update_count),
            .i_direction(1'b0),
            .i_load_value(next_count),
            .o_count(in_flight),
            .o_overflow(unused_overflow),
            .o_underflow(unused_underflow),
            .o_terminal(unused_terminal)
        );

        assign live_fault = (i_rstb === 1'b1) && (identity_fault || ownership_fault ||
            conversion_fault || table_bad || interpolation_fault);
        assign o_busy = in_flight != '0 || o_fatal_error || live_fault;
        assign o_idle = !o_busy;
        assign o_quiescent = o_idle && controls_known && i_rstb === 1'b1 &&
            i_flush === 1'b0 && i_drain === 1'b0 && i_request_valid === 1'b0 &&
            i_error_clear === 1'b0;
        assign o_drain_done = controls_known && i_flush === 1'b0 &&
            i_rstb === 1'b1 && i_drain === 1'b1 && o_idle;

        exp_error_t current_error;
        logic [5:0] error_next;
        always_comb begin
            current_error = EXP_ERR_NONE;

            if (accepted &&!legal) begin
                if (unsupported_base) current_error = EXP_ERR_BASE;
                else current_error = EXP_ERR_INTERPOLATION;
            end
            if (run && valid[2] && ready[2] && table_corrected) current_error = EXP_ERR_CORRECTED;
            if (i_rstb !== 1'b0 && (!controls_known ||
                (i_request_valid === 1'b1 &&!fields_known))) current_error = EXP_ERR_UNKNOWN;
            error_next = {o_error, o_fatal_error, o_error_code};
            if (live_fault) begin
                error_next = {1'b1, 1'b1, EXP_ERR_ARITHMETIC};
                if (ownership_fault) error_next = {1'b1, 1'b1, EXP_ERR_OWNERSHIP};
                if (table_bad) error_next = {1'b1, 1'b1, EXP_ERR_TABLE};
                if (conversion_fault) error_next = {1'b1, 1'b1, EXP_ERR_RANGE};
                if (identity_fault) error_next = {1'b1, 1'b1, EXP_ERR_IDENTITY};
            end else if (!o_fatal_error) begin
                if (flush || (o_idle && controls_known && i_error_clear &&!i_request_valid &&
                    !i_drain)) error_next = '0;
                else if (!o_error && current_error != EXP_ERR_NONE)
                    error_next = {1'b1, 1'b0, current_error};
            end
        end

        dff #(.WIDTH(6), .ASYNC_RESET(ASYNC_RESET != 0)) u_errors (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(1'b1),
            .i_d(error_next),
            .o_q({o_error, o_fatal_error, o_error_code})
        );

        control_t accepted_control;
        wire [CONTROL-1:0] unused_accepted_control_fields = accepted_control;
        assign accepted_control = next_control[0];
        control_t completing_control;
        wire [CONTROL-1:0] unused_completing_control_fields = completing_control;
        assign completing_control = control_bits[L];
        wire [11:0] events_next;
        assign events_next[0] = accepted;
        assign events_next[1] = result_create;
        assign events_next[2] = i_rstb === 1'b1 && i_request_valid === 1'b1 &&!o_request_ready;
        assign events_next[3] = o_result_valid && i_result_ready === 1'b0;
        assign events_next[4] = accepted && accepted_control.active &&!accepted_control.base;
        assign events_next[5] = accepted && accepted_control.active && accepted_control.base;
        assign events_next[6] = run && valid[2] && ready[2] && table_control.active;
        assign events_next[7] = run && valid[3] && ready[3] &&
            interpolate_control.active && interpolate_control.interpolate;
        assign events_next[8] = result_create && completing_control.active && stage_data[L][2];
        assign events_next[9] = result_create && completing_control.active && stage_data[L][1];
        assign events_next[10] = run && valid[2] && ready[2] && table_corrected;
        assign events_next[11] = permit && table_bad;

        dff #(.WIDTH(12), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(1'b1),
            .i_d(events_next),
            .o_q({o_event_table_uncorrectable, o_event_table_corrected, o_event_underflow,
                o_event_overflow, o_event_interpolation, o_event_table_lookup, o_event_base_2,
                o_event_base_e, o_event_result_stall, o_event_request_stall,
                o_event_result_complete, o_event_request_accept})
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_flushed (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(1'b1),
            .i_d(flush && in_flight != '0),
            .o_q(o_flushed)
        );
`ifdef MOSAIC_EXP_UNIT_ASSERTIONS
        exp_unit_assertions #(
            .CAPACITY(L + QD),
            .COUNT_WIDTH(COUNT_WIDTH),
            .RESPONSE(RESPONSE),
            .RW(RW),
            .RF(RF),
            .EW(EW),
            .I(I)
        ) u_assertions (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(flush),
            .i_run(run),
            .i_fatal(o_fatal_error || live_fault),
            .i_accept(accepted),
            .i_pop(result_pop),
            .i_occupancy(in_flight),
            .i_valid(o_result_valid),
            .i_ready(i_result_ready),
            .i_payload(queue_output),
            .i_request_ready(o_request_ready),
            .i_floor_active(run && valid[2] && table_control.active),
            .i_z($signed(z2)),
            .i_k($signed(z2[RW-1:RF])),
            .i_fraction(z2[RF-1:0]),
            .i_interpolate(run && valid[3] && interpolate_control.active &&
                interpolate_control.interpolate),
            .i_lower(lower3),
            .i_upper(upper3),
            .i_mantissa(mantissa)
        );
`endif
    end
endmodule
