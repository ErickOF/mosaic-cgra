`timescale 1ns / 1ps
`default_nettype none
// Reflected CRC-32C over low byte first, including canonical zero padding.
module configuration_network_crc #(
    parameter int WIDTH = 64,
    localparam int BYTES = (WIDTH + 7) / 8
) (
    input wire [WIDTH-1:0] i_data,
    output logic [31:0] o_crc
);
    always @* begin
        logic [BYTES*8-1:0] padded;
        logic [31:0] crc;
        padded = (BYTES*8)'(i_data);
        crc = 32'hffffffff;
        for (int b = 0; b < BYTES; b++) begin
            crc ^= {24'b0, padded[b*8+:8]};
            for (int k = 0; k < 8; k++)
                crc = crc[0] ? (crc >> 1) ^ 32'h82f63b78 : crc >> 1;
        end
        o_crc = ~crc;
    end
endmodule
`default_nettype wire
