`timescale 1ns / 1ps
// Runtime selection among statically elaborated common packer configurations.
// A position has 2**lane_log2 lanes, each an explicitly selected integer width.
module mst_element_converter #(
    parameter int DATA_WIDTH = 128,
    parameter int SUPPORT_CONVERSION = 1,
    localparam int D = DATA_WIDTH,
    localparam int Y = D / 8,
    localparam int LOG = $clog2(Y),
    localparam int SZ = LOG > 0 ? $clog2(LOG + 1) : 1,
    localparam int CHOICES = (LOG + 1) ** 3
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_valid,
    output wire o_ready,
    input wire [D-1:0] i_data,
    input wire [SZ-1:0] i_source_log2,
    input wire [SZ-1:0] i_destination_log2,
    input wire [SZ-1:0] i_lane_log2,
    input wire i_signed,
    input wire i_saturate,
    input wire i_reverse,
    output wire o_valid,
    input wire i_ready,
    output logic [D-1:0] o_data,
    output logic o_overflow,
    output logic o_saturated,
    output wire o_error
);
    wire [CHOICES-1:0] selected;
    wire [CHOICES-1:0] valid;
    wire [CHOICES-1:0] ready;
    wire [CHOICES-1:0] overflow;
    wire [CHOICES-1:0] saturated;
    wire [CHOICES-1:0] bad;
    wire [D-1:0] data [CHOICES];

    for (genvar source = 0; source <= LOG; source++) begin : g_source
        for (genvar destination = 0; destination <= LOG; destination++) begin : g_destination
            for (genvar lanes = 0; lanes <= LOG; lanes++) begin : g_lanes
                localparam int INDEX = (source * (LOG + 1) + destination) * (LOG + 1) + lanes;
                assign selected[INDEX] = i_source_log2 == SZ'(source) &&
                    i_destination_log2 == SZ'(destination) && i_lane_log2 == SZ'(lanes);

                if (source + lanes <= LOG && destination + lanes <= LOG &&
                    (SUPPORT_CONVERSION == 1 || source == destination)) begin : g_supported
                    localparam int SOURCE_BITS = 8 << source;
                    localparam int DESTINATION_BITS = 8 << destination;
                    localparam int ELEMENTS = 1 << lanes;
                    localparam bit NARROWING = SOURCE_BITS > DESTINATION_BITS;
                    wire [DESTINATION_BITS*ELEMENTS-1:0] result;

                    packer #(
                        .NUM_ELEMENTS(ELEMENTS),
                        .SRC_ELEMENT_WIDTH(SOURCE_BITS),
                        .DST_ELEMENT_WIDTH(DESTINATION_BITS),
                        .USER_WIDTH(1)
                    ) u_packer (
                        .i_clk(i_clk),
                        .i_rstb(i_rstb),
                        .i_flush(1'b0),
                        .i_valid(i_valid && selected[INDEX]),
                        .o_ready(ready[INDEX]),
                        .i_data(i_data[0+:SOURCE_BITS*ELEMENTS]),
                        .i_lane_valid({ELEMENTS{1'b1}}),
                        .i_signed(i_signed),
                        .i_saturate(NARROWING ? i_saturate : 1'b0),
                        .i_reverse(i_reverse),
                        .i_last(1'b1),
                        .i_user(1'b0),
                        .o_valid(valid[INDEX]),
                        .i_ready(i_ready),
                        .o_data(result),
                        .o_lane_valid(),
                        .o_overflow(),
                        .o_saturated(),
                        .o_any_overflow(overflow[INDEX]),
                        .o_any_saturated(saturated[INDEX]),
                        .o_last(),
                        .o_user(),
                        .o_config_error(bad[INDEX]),
                        .o_busy()
                    );

                    assign data[INDEX] = D'(result);
                end else begin : g_absent
                    assign data[INDEX] = '0;
                    assign valid[INDEX] = 1'b0;
                    assign ready[INDEX] = 1'b0;
                    assign overflow[INDEX] = 1'b0;
                    assign saturated[INDEX] = 1'b0;
                    assign bad[INDEX] = i_valid && selected[INDEX];
                end
            end
        end
    end

    assign o_ready = |(ready & selected);
    assign o_valid = |valid;
    assign o_error = (|bad) || (i_valid && (^ {i_source_log2, i_destination_log2,
        i_lane_log2, i_signed, i_saturate, i_reverse} === 1'bx));

    always @* begin
        o_data = '0;
        o_overflow = 1'b0;
        o_saturated = 1'b0;

        for (int choice = 0; choice < CHOICES; choice++) begin
            if (selected[choice] && valid[choice]) begin
                o_data = data[choice];
                o_overflow |= overflow[choice];
                o_saturated |= saturated[choice];
            end
        end
    end
endmodule
