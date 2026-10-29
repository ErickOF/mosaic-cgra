`timescale 1ns / 1ps
// Independent, stable level acknowledgements only. Pulse/data CDC needs an
// external handshake adapter; this chain does not synchronize a transaction bus.
module cluster_power_manager_sync #(
    parameter int WIDTH = 1,
    parameter int STAGES = 2,
    parameter bit ASYNCHRONOUS = 1
) (
    input wire i_clk,
    input wire i_rstb,
    input wire [WIDTH-1:0] i_status,
    output wire [WIDTH-1:0] o_status
);
    if (ASYNCHRONOUS) begin : g_async
        (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
        wire [WIDTH*STAGES-1:0] pipeline;

        dff #(
            .WIDTH(WIDTH * STAGES),
            .HAS_ENABLE(0)
        ) u_stages (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(1'b1),
            .i_d({pipeline[WIDTH*(STAGES-1)-1:0], i_status}),
            .o_q(pipeline)
        );

        assign o_status = pipeline[WIDTH*(STAGES-1)+:WIDTH];
    end else begin : g_synchronous
        assign o_status = i_status;
    end
endmodule
