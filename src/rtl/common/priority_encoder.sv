`timescale 1ns / 1ps

// Select one request according to a fixed elaboration-time priority direction.
module priority_encoder #(
    parameter int unsigned WIDTH = 4,
    parameter bit LSB_HIGH_PRIORITY = 1'b1,
    parameter int unsigned INDEX_WIDTH = (WIDTH > 1) ? $clog2(WIDTH) : 1
) (
    input  logic [      WIDTH-1:0] i_request,
    output logic                   o_valid,
    output logic [INDEX_WIDTH-1:0] o_index,
    output logic [      WIDTH-1:0] o_onehot,
    output logic                   o_multiple
);
    localparam int unsigned ExpectedIndexWidth = (WIDTH > 1) ? $clog2(WIDTH) : 1;

    if (WIDTH < 1) begin : gen_invalid_width
        initial $fatal(1, "WIDTH must be greater than or equal to one");
    end
    if (INDEX_WIDTH != ExpectedIndexWidth) begin : gen_invalid_index_width
        initial $fatal(1, "INDEX_WIDTH must match the width derived from WIDTH");
    end

    always_comb begin
        logic request_seen;

        o_valid = |i_request;
        o_index = '0;
        o_onehot = '0;
        o_multiple = 1'b0;
        request_seen = 1'b0;

        if (LSB_HIGH_PRIORITY) begin
            for (int unsigned position = WIDTH; position > 0; position--) begin
                if (i_request[position-1]) begin
                    o_index = INDEX_WIDTH'(position - 1);
                    o_onehot = WIDTH'(1'b1) << (position - 1);
                    o_multiple = o_multiple | request_seen;
                    request_seen = 1'b1;
                end
            end
        end else begin
            for (int unsigned position = 0; position < WIDTH; position++) begin
                if (i_request[position]) begin
                    o_index = INDEX_WIDTH'(position);
                    o_onehot = WIDTH'(1'b1) << position;
                    o_multiple = o_multiple | request_seen;
                    request_seen = 1'b1;
                end
            end
        end
    end
endmodule
