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
        priority_encoder_width_must_be_greater_than_zero invalid_width ();
    end
    if (INDEX_WIDTH != ExpectedIndexWidth) begin : gen_invalid_index_width
        priority_encoder_index_width_must_match_width invalid_index_width ();
    end

    // Exclude the datapath for invalid parameters so its casts/indexing cannot
    // obscure the intended elaboration guard diagnostic.
    if (WIDTH >= 1 && INDEX_WIDTH == ExpectedIndexWidth) begin : gen_encoder
        always_comb begin
            logic request_seen;
            logic known_seen, known_multiple;
            logic unknown_seen, unknown_multiple;

            o_valid = |i_request;
            o_index = '0;
            o_onehot = '0;
            request_seen = 1'b0;
            known_seen = 1'b0;
            known_multiple = 1'b0;
            unknown_seen = 1'b0;
            unknown_multiple = 1'b0;

            // Traverse highest priority first. The first possible request
            // fixes the selection: a known one wins, while X/Z makes it
            // ambiguous and cannot be skipped in favor of a lower request.
            for (int unsigned position = 0; position < WIDTH; position++) begin
                int unsigned request_index;
                request_index = LSB_HIGH_PRIORITY ? position : WIDTH - position - 1;
                case (i_request[request_index])
                    1'b0: begin end
                    1'b1: begin
                        known_multiple = known_multiple | known_seen;
                        known_seen = 1'b1;
                        if (!request_seen) begin
                            o_index = INDEX_WIDTH'(request_index);
                            o_onehot = WIDTH'(1'b1) << request_index;
                            request_seen = 1'b1;
                        end
                    end
                    default: begin
                        unknown_multiple = unknown_multiple | unknown_seen;
                        unknown_seen = 1'b1;
                        if (!request_seen) begin
                            o_index = 'x;
                            o_onehot = 'x;
                            request_seen = 1'b1;
                        end
                    end
                endcase
            end

            // Known ones establish a minimum request count. Unknown bits
            // may increase it: report X only if contention is undecidable.
            if (known_multiple) o_multiple = 1'b1;
            else if ((known_seen && unknown_seen) || unknown_multiple) o_multiple = 1'bx;
            else o_multiple = 1'b0;
        end
    end
endmodule
