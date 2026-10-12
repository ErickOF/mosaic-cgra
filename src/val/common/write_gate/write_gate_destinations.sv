/// Verification-only destinations: one masked register and four masked words.
/// The architectural DUT is combinational; this fixture adds capture boundaries.
module write_gate_destinations #(
    parameter int unsigned WIDTH = 1
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_capture_valid,
    input logic i_destination,
    input logic [1:0] i_address,
    input logic [WIDTH-1:0] i_write_data,
    input logic [WIDTH-1:0] i_write_enable,
    input logic [WIDTH-1:0] i_suppress,
    output wire [WIDTH-1:0] o_write_enable,
    output wire [WIDTH-1:0] o_write_suppressed,
    output logic [WIDTH-1:0] o_register_state,
    output wire [4*WIDTH-1:0] o_memory_state
);
    logic [WIDTH-1:0] memory [0:3];

    write_gate #(.WIDTH(WIDTH)) u_gate (
        .i_write_enable(i_write_enable), .i_suppress(i_suppress),
        .o_write_enable(o_write_enable), .o_write_suppressed(o_write_suppressed)
    );

    for (genvar word_index = 0; word_index < 4; word_index++) begin : g_observe_word
        assign o_memory_state[word_index*WIDTH +: WIDTH] = memory[word_index];
    end

    always_ff @(posedge i_clk or negedge i_rstb) begin
        if (!i_rstb) begin
            o_register_state <= '0;
            for (int word_index = 0; word_index < 4; word_index++) begin
                memory[word_index] <= '0;
            end
        end else if (i_capture_valid) begin
            // A vector update preserves every disabled bit and avoids variable
            // array bit assignments that some simulator versions cannot lint.
            if (i_destination) begin
                memory[i_address] <= (memory[i_address] & ~o_write_enable)
                    | (i_write_data & o_write_enable);
            end else begin
                o_register_state <= (o_register_state & ~o_write_enable)
                    | (i_write_data & o_write_enable);
            end
        end
    end
endmodule
