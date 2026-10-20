`timescale 1ns / 1ps

// Fixed channel partitions of a shared delay-stage budget. Channel identities
// and context delay fields are supplied by the integrating mapper/controller.
module rdu #(
    parameter DATA_WIDTH = 32,
    parameter NUM_CHANNELS = 2,
    parameter TOTAL_DELAY_ENTRIES = 8,
    // Other geometries require an explicit, exactly sized packed allocation.
    parameter CHANNEL_CAPACITY = (NUM_CHANNELS == 2 && TOTAL_DELAY_ENTRIES == 8) ? 8'h44 : 8'bx,
    parameter ASYNC_RESET = 0,
    localparam bit DIMENSIONS_VALID =
        ((DATA_WIDTH >= 1) === 1'b1) && (^DATA_WIDTH !== 1'bx) &&
        ((NUM_CHANNELS >= 1) === 1'b1) && (^NUM_CHANNELS !== 1'bx) &&
        ((TOTAL_DELAY_ENTRIES >= 0) === 1'b1) && (^TOTAL_DELAY_ENTRIES !== 1'bx) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    localparam int unsigned DATA_BITS = DIMENSIONS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned CHANNELS = DIMENSIONS_VALID ? NUM_CHANNELS : 1,
    localparam int unsigned ENTRIES = DIMENSIONS_VALID ? TOTAL_DELAY_ENTRIES : 0,
    localparam int unsigned CAPACITY_WIDTH = ENTRIES > 0 ? $clog2(64'(ENTRIES) + 1) : 1,
    localparam int unsigned DELAY_WIDTH = CAPACITY_WIDTH,
    localparam int unsigned CHANNEL_DATA_WIDTH = CHANNELS * DATA_BITS,
    localparam int unsigned DELAY_BUS_WIDTH = CHANNELS * DELAY_WIDTH,
    localparam int unsigned CAPACITY_BUS_WIDTH = CHANNELS * CAPACITY_WIDTH,
    // The zero-budget fallback is a constant wire, never a storage element.
    localparam int unsigned STORAGE_SLOTS = ENTRIES > 0 ? ENTRIES : 1
) (
    input  logic                          i_clk,
    input  logic                          i_rstb,
    input  logic                          i_advance,
    input  logic [CHANNELS-1:0]           i_channel_enable,
    input  logic [DELAY_BUS_WIDTH-1:0]    i_delay,
    input  logic [CHANNEL_DATA_WIDTH-1:0] i_input_data,
    input  logic [CHANNELS-1:0]           i_input_valid,
    input  logic [CHANNELS-1:0]           i_flush,
    output logic [CHANNEL_DATA_WIDTH-1:0] o_output_data,
    output logic [CHANNELS-1:0]           o_output_valid,
    output logic [CHANNELS-1:0]           o_output_transfer,
    output logic [CHANNELS-1:0]           o_channel_empty,
    output logic                          o_all_empty,
    output logic [CHANNELS-1:0]           o_config_error
);
    function automatic bit allocation_valid();
        logic [63:0] total;
        total = '0;
        allocation_valid = 1'b0;
        if ($bits(CHANNEL_CAPACITY) == CAPACITY_BUS_WIDTH && ^CHANNEL_CAPACITY !== 1'bx) begin
            allocation_valid = 1'b1;
            for (int c = 0; c < CHANNELS; c++) begin
                if (64'(CHANNEL_CAPACITY[c*CAPACITY_WIDTH+:CAPACITY_WIDTH]) > 64'(ENTRIES))
                    allocation_valid = 1'b0;
                total += 64'(CHANNEL_CAPACITY[c*CAPACITY_WIDTH+:CAPACITY_WIDTH]);
            end
            if (total != 64'(ENTRIES)) allocation_valid = 1'b0;
        end
    endfunction

    function automatic int unsigned channel_base(input int unsigned channel);
        int unsigned base;
        base = 0;
        for (int unsigned c = 0; c < channel; c++) begin
            base += 32'(CHANNEL_CAPACITY[c*CAPACITY_WIDTH+:CAPACITY_WIDTH]);
        end
        channel_base = base;
    endfunction

    if (!DIMENSIONS_VALID || !allocation_valid()) begin : g_invalid_parameters
        rdu_parameters_must_be_valid invalid_parameters ();
    end else begin : g_rdu
        logic [STORAGE_SLOTS*DATA_BITS-1:0] delay_data;
        logic [STORAGE_SLOTS-1:0] delay_valid;

        if (ENTRIES == 0) begin : g_no_storage
            assign delay_data = '0;
            assign delay_valid = '0;
        end

        for (genvar c = 0; c < CHANNELS; c++) begin : g_channel
            localparam int unsigned CAPACITY = 32'(CHANNEL_CAPACITY[c*CAPACITY_WIDTH+:CAPACITY_WIDTH]);
            localparam int unsigned BASE = channel_base(c);
            wire [DELAY_WIDTH-1:0] selected_delay = i_delay[c*DELAY_WIDTH+:DELAY_WIDTH];
            logic delay_legal;
            logic [DATA_BITS-1:0] selected_data;
            logic selected_valid;

            assign delay_legal = (^selected_delay === 1'bx) ? 1'bx :
                (selected_delay <= DELAY_WIDTH'(CAPACITY));
            assign o_config_error[c] = i_channel_enable[c] && !delay_legal;

            for (genvar stage = 0; stage < CAPACITY; stage++) begin : g_stage
                localparam int unsigned ENTRY = BASE + stage;
                logic source_valid, advance_stage, next_valid, write_data;
                logic [DATA_BITS-1:0] source_data;
                if (stage == 0) begin : g_input
                    assign source_valid = i_input_valid[c];
                    assign source_data = i_input_data[c*DATA_BITS+:DATA_BITS];
                end else begin : g_previous
                    assign source_valid = delay_valid[ENTRY-1];
                    assign source_data = delay_data[(ENTRY-1)*DATA_BITS+:DATA_BITS];
                end
                assign advance_stage = i_advance && i_channel_enable[c] && delay_legal &&
                    (selected_delay > DELAY_WIDTH'(stage));
                // Flush invalidates the whole partition, even while disabled
                // or stalled and including stages above the selected delay.
                assign next_valid = i_flush[c] ? 1'b0 :
                    (advance_stage ? source_valid : delay_valid[ENTRY]);
                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(1'b1),
                    .i_d(next_valid),
                    .o_q(delay_valid[ENTRY])
                );

                // Payload has no reset. Reset/flush suppress writes; bubbles,
                // inactive stages, bypass and stalls preserve every data bit.
                assign write_data = i_rstb && !i_flush[c] && advance_stage && source_valid;
                always_ff @(posedge i_clk) begin
                    case (write_data)
                        1'b0: begin end
                        1'b1: delay_data[ENTRY*DATA_BITS+:DATA_BITS] <= source_data;
                        default: delay_data[ENTRY*DATA_BITS+:DATA_BITS] <= 'x;
                    endcase
                end
            end

            if (CAPACITY == 0) begin : g_zero_capacity
                assign o_channel_empty[c] = 1'b1;
            end else begin : g_empty
                // Empty describes ALL allocated validity, independently of
                // enable, selected delay, reset clamping or an unclocked flush.
                assign o_channel_empty[c] = !(|delay_valid[BASE+:CAPACITY]);
            end

            always_comb begin
                selected_data = '0;
                selected_valid = 1'b0;
                case (i_rstb && !i_flush[c] && i_channel_enable[c])
                    1'b0: begin end
                    1'b1: begin
                        case (delay_legal)
                            1'b0: begin end
                            1'b1: begin
                                if (selected_delay == '0) begin
                                    selected_data = i_input_data[c*DATA_BITS+:DATA_BITS];
                                    selected_valid = i_input_valid[c];
                                end else if (CAPACITY > 0) begin
                                    selected_data = delay_data[(BASE+32'(selected_delay)-1)*DATA_BITS+:DATA_BITS];
                                    selected_valid = delay_valid[BASE+32'(selected_delay)-1];
                                end
                            end
                            default: begin
                                selected_data = 'x;
                                selected_valid = 1'bx;
                            end
                        endcase
                    end
                    default: begin
                        selected_data = 'x;
                        selected_valid = 1'bx;
                    end
                endcase
            end
            assign o_output_valid[c] = selected_valid;
            assign o_output_transfer[c] = i_advance && selected_valid;
            operand_isolation #(.WIDTH(DATA_BITS)) u_output_data (
                .i_data(selected_data),
                .i_isolate(!selected_valid),
                .o_data(o_output_data[c*DATA_BITS+:DATA_BITS])
            );
        end
        assign o_all_empty = &o_channel_empty;
    end
endmodule
