`timescale 1ns / 1ps

// Single-clock weighted-event bank. Event slots are supplied by the integration;
// this generic primitive does not assign architectural event or owner IDs.
module performance_counters #(
    parameter COUNTER_WIDTH = 48,
    parameter NUM_COUNTERS = 10,
    parameter NUM_EVENTS = 16,
    parameter INCREMENT_WIDTH = 16,
    parameter SATURATE = 1,
    parameter HAS_SNAPSHOT = 1,
    parameter HAS_THRESHOLD = 1,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((COUNTER_WIDTH >= 1) === 1'b1) && (^COUNTER_WIDTH !== 1'bx) &&
        ((NUM_COUNTERS >= 1) === 1'b1) && (^NUM_COUNTERS !== 1'bx) &&
        ((NUM_EVENTS >= 1) === 1'b1) && (^NUM_EVENTS !== 1'bx) &&
        ((INCREMENT_WIDTH >= 1) === 1'b1) && (^INCREMENT_WIDTH !== 1'bx) &&
        ((SATURATE === 0) || (SATURATE === 1)) &&
        ((HAS_SNAPSHOT === 0) || (HAS_SNAPSHOT === 1)) &&
        ((HAS_THRESHOLD === 0) || (HAS_THRESHOLD === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    // Safe fallback dimensions let illegal arguments reach the named guard.
    localparam int unsigned COUNT_BITS = PARAMETERS_VALID ? COUNTER_WIDTH : 1,
    localparam int unsigned COUNTERS = PARAMETERS_VALID ? NUM_COUNTERS : 1,
    localparam int unsigned EVENTS = PARAMETERS_VALID ? NUM_EVENTS : 1,
    localparam int unsigned INCREMENT_BITS = PARAMETERS_VALID ? INCREMENT_WIDTH : 1,
    localparam int unsigned COUNTER_ADDR_WIDTH = COUNTERS > 1 ? $clog2(COUNTERS) : 1,
    localparam int unsigned EVENT_ADDR_WIDTH = EVENTS > 1 ? $clog2(EVENTS) : 1,
    localparam int unsigned EVENT_SELECT_WIDTH = COUNTERS * EVENT_ADDR_WIDTH,
    localparam int unsigned EVENT_INCREMENT_WIDTH = EVENTS * INCREMENT_BITS,
    localparam int unsigned THRESHOLD_BUS_WIDTH = COUNTERS * COUNT_BITS,
    localparam int unsigned SUM_WIDTH =
        (COUNT_BITS > INCREMENT_BITS ? COUNT_BITS : INCREMENT_BITS) + 1
) (
    input  logic                             i_clk,
    input  logic                             i_rstb,
    input  logic                             i_global_enable,
    input  logic                             i_freeze,
    input  logic [COUNTERS-1:0]              i_counter_enable,
    input  logic [COUNTERS-1:0]              i_clear,
    input  logic [EVENT_SELECT_WIDTH-1:0]    i_event_select,
    input  logic [EVENTS-1:0]                i_event_valid,
    input  logic [EVENT_INCREMENT_WIDTH-1:0] i_event_increment,
    input  logic [COUNTERS-1:0]              i_threshold_enable,
    input  logic [THRESHOLD_BUS_WIDTH-1:0]   i_threshold_value,
    input  logic                             i_snapshot,
    input  logic                             i_read_enable,
    input  logic                             i_read_snapshot,
    input  logic [COUNTER_ADDR_WIDTH-1:0]    i_read_index,
    output logic [COUNT_BITS-1:0]           o_read_data,
    output logic                             o_read_overflow,
    output logic                             o_read_valid,
    output logic [COUNTERS-1:0]             o_counter_overflow,
    output logic [COUNTERS-1:0]             o_threshold_event,
    output logic [COUNTERS-1:0]             o_config_error,
    output logic                             o_snapshot_valid
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        performance_counters_parameters_must_be_valid invalid_parameters ();
    end else begin : g_bank
        // Explicit replication also preserves the intended width in synthesis
        // frontends when this constant participates in conditional expressions.
        localparam logic [COUNT_BITS-1:0] MAX_COUNT = {COUNT_BITS{1'b1}};
        logic [THRESHOLD_BUS_WIDTH-1:0] live_counts, next_counts, snapshot_counts;
        logic [COUNTERS-1:0] next_overflow, snapshot_overflow;

        for (genvar c = 0; c < COUNTERS; c++) begin : g_counter
            wire [EVENT_ADDR_WIDTH-1:0] selection = i_event_select[c*EVENT_ADDR_WIDTH+:EVENT_ADDR_WIDTH];
            wire [COUNT_BITS-1:0] value = live_counts[c*COUNT_BITS+:COUNT_BITS];
            logic selection_legal, threshold_legal, monitoring, update_request;
            logic selected_valid, at_saturation, arithmetic_enable, overflow;
            logic [INCREMENT_BITS-1:0] selected_increment, isolated_increment;
            logic [COUNT_BITS-1:0] isolated_count, result;
            logic [SUM_WIDTH-1:0] wide_sum;

            assign monitoring = i_global_enable && i_counter_enable[c];
            // An extra comparison bit prevents power-of-two counts truncating
            // to zero. Unknown active selectors stay unknown instead of aliasing.
            assign selection_legal = (^selection === 1'bx) ? 1'bx :
                ({1'b0, selection} < (EVENT_ADDR_WIDTH+1)'(EVENTS));
            if (HAS_THRESHOLD == 1) begin : g_threshold_configuration
                wire [COUNT_BITS-1:0] threshold = i_threshold_value[c*COUNT_BITS+:COUNT_BITS];
                assign threshold_legal = !i_threshold_enable[c] ||
                    ((^threshold === 1'bx) ? 1'bx : (threshold != '0));
            end else begin : g_no_threshold_configuration
                assign threshold_legal = 1'b1;
            end
            // Freeze suppresses updates, but configuration diagnostics remain
            // visible for a globally and individually enabled counter.
            assign o_config_error[c] = monitoring && !(selection_legal && threshold_legal);

            always_comb begin
                selected_valid = 1'b0;
                selected_increment = '0;
                case (i_rstb && monitoring && !i_freeze && !i_clear[c] &&
                      selection_legal && threshold_legal)
                    1'b0: begin end
                    1'b1: begin
                        selected_valid = i_event_valid[selection];
                        selected_increment = i_event_increment[selection*INCREMENT_BITS+:INCREMENT_BITS];
                    end
                    default: begin
                        selected_valid = 1'bx;
                        selected_increment = 'x;
                    end
                endcase
            end
            assign update_request = selected_valid && (selected_increment != '0);
            if (SATURATE == 1) begin : g_saturating
                assign at_saturation = value == MAX_COUNT;
                assign result = overflow ? MAX_COUNT : wide_sum[COUNT_BITS-1:0];
            end else begin : g_wrapping
                assign at_saturation = 1'b0;
                assign result = wide_sum[COUNT_BITS-1:0];
            end
            assign arithmetic_enable = update_request && !at_saturation;

            // Gate both operands, including event-valid zero, legal no-ops, and
            // already saturated counters. Preserve the full increment width.
            operand_isolation #(.WIDTH(COUNT_BITS)) u_count_operand (
                .i_data(value),
                .i_isolate(!arithmetic_enable),
                .o_data(isolated_count)
            );
            operand_isolation #(.WIDTH(INCREMENT_BITS)) u_increment_operand (
                .i_data(selected_increment),
                .i_isolate(!arithmetic_enable),
                .o_data(isolated_increment)
            );
            assign wide_sum = SUM_WIDTH'(isolated_count) + SUM_WIDTH'(isolated_increment);
            assign overflow = |wide_sum[SUM_WIDTH-1:COUNT_BITS];

            always_comb begin
                next_counts[c*COUNT_BITS+:COUNT_BITS] = value;
                next_overflow[c] = o_counter_overflow[c];
                case (i_clear[c])
                    1'b1: begin
                        next_counts[c*COUNT_BITS+:COUNT_BITS] = '0;
                        next_overflow[c] = 1'b0;
                    end
                    1'b0: begin
                        case (update_request)
                            1'b0: begin end
                            1'b1: begin
                                next_counts[c*COUNT_BITS+:COUNT_BITS] = at_saturation ? MAX_COUNT : result;
                                // Reaching MAX exactly is not overflow. A later
                                // positive request at MAX must set sticky status.
                                next_overflow[c] = o_counter_overflow[c] || at_saturation || overflow;
                            end
                            default: begin
                                next_counts[c*COUNT_BITS+:COUNT_BITS] = 'x;
                                next_overflow[c] = 1'bx;
                            end
                        endcase
                    end
                    default: begin
                        next_counts[c*COUNT_BITS+:COUNT_BITS] = 'x;
                        next_overflow[c] = 1'bx;
                    end
                endcase
            end
            dff #(.WIDTH(COUNT_BITS), .ASYNC_RESET(ASYNC_RESET != 0)) u_value (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(1'b1),
                .i_d(next_counts[c*COUNT_BITS+:COUNT_BITS]),
                .o_q(live_counts[c*COUNT_BITS+:COUNT_BITS])
            );
            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_overflow (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(1'b1),
                .i_d(next_overflow[c]),
                .o_q(o_counter_overflow[c])
            );
            if (HAS_THRESHOLD == 1) begin : g_threshold
                wire [COUNT_BITS-1:0] threshold = i_threshold_value[c*COUNT_BITS+:COUNT_BITS];
                logic threshold_next;
                // For wrap, compare before truncation so a large crossing is
                // observed even when the stored result falls below threshold.
                assign threshold_next = !i_clear[c] && update_request && i_threshold_enable[c] &&
                    (value < threshold) &&
                    (SATURATE == 1 ? (result >= threshold) : (wide_sum >= SUM_WIDTH'(threshold)));
                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_pulse (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(1'b1),
                    .i_d(threshold_next),
                    .o_q(o_threshold_event[c])
                );
            end else begin : g_no_threshold
                assign o_threshold_event[c] = 1'b0;
            end
        end

        if (HAS_SNAPSHOT == 1) begin : g_snapshot
            // Shadow payload has no reset. Capture NEXT values atomically so
            // a coincident clear/update is visible in the same snapshot.
            always_ff @(posedge i_clk) begin
                if (i_rstb) begin
                    case (i_snapshot)
                        1'b0: begin end
                        1'b1: begin
                            snapshot_counts <= next_counts;
                            snapshot_overflow <= next_overflow;
                        end
                        default: begin
                            snapshot_counts <= 'x;
                            snapshot_overflow <= 'x;
                        end
                    endcase
                end
            end
            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(1'b1),
                .i_d(i_snapshot ? 1'b1 : o_snapshot_valid),
                .o_q(o_snapshot_valid)
            );
        end else begin : g_no_snapshot
            assign snapshot_counts = '0;
            assign snapshot_overflow = '0;
            assign o_snapshot_valid = 1'b0;
        end

        always_comb begin
            o_read_data = '0;
            o_read_overflow = 1'b0;
            o_read_valid = 1'b0;
            case (i_read_enable)
                1'b0: begin end
                1'b1: begin
                    if (^i_read_index === 1'bx) begin
                        o_read_data = 'x;
                        o_read_overflow = 1'bx;
                        o_read_valid = 1'bx;
                    end else if ({1'b0, i_read_index} < (COUNTER_ADDR_WIDTH+1)'(COUNTERS)) begin
                        case (i_read_snapshot)
                            1'b0: begin
                                o_read_data = live_counts[i_read_index*COUNT_BITS+:COUNT_BITS];
                                o_read_overflow = o_counter_overflow[i_read_index];
                                o_read_valid = 1'b1;
                            end
                            1'b1: begin
                                if (HAS_SNAPSHOT == 1) begin
                                    o_read_data = o_snapshot_valid ? snapshot_counts[i_read_index*COUNT_BITS+:COUNT_BITS] : '0;
                                    o_read_overflow = o_snapshot_valid ? snapshot_overflow[i_read_index] : 1'b0;
                                    o_read_valid = o_snapshot_valid;
                                end
                            end
                            default: begin
                                o_read_data = 'x;
                                o_read_overflow = 1'bx;
                                o_read_valid = 1'bx;
                            end
                        endcase
                    end
                end
                default: begin
                    o_read_data = 'x;
                    o_read_overflow = 1'bx;
                    o_read_valid = 1'bx;
                end
            endcase
        end
    end
endmodule
