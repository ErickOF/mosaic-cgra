`timescale 1ns / 1ps

package crc_pkg;
    // One reflected CRC-32C step. Feedback is the outgoing CRC bit XOR input bit.
    // Keep the conditional merge so unknown feedback preserves four-state behavior.
    function automatic logic [31:0] crc32c_step(
        input logic [31:0] crc,
        input logic feedback
    );
        return feedback ? (crc >> 1) ^ 32'h82f63b78 : crc >> 1;
    endfunction

    // Consume one byte, least-significant bit first, without initial/final XORs.
    // Each caller owns its image order, padding, initial state and final complement.
    function automatic logic [31:0] crc32c_byte(
        input logic [31:0] crc,
        input logic [7:0] value
    );
        logic [31:0] result;
        result = crc ^ {24'b0, value};

        for (int bit_index = 0; bit_index < 8; bit_index++)
            result = crc32c_step(result, result[0]);

        return result;
    endfunction
endpackage
