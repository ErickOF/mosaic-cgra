`timescale 1ns / 1ps

// Geometry shared by the shortened Hamming codec and its protected containers.
// Callers validate data widths and protection modes before using these helpers.
package ecc_pkg;
    function automatic int hamming_bits(input int width);
        int count;
        count = 1;

        // Wide intermediates keep the sizing calculation independent of int overflow.
        while ((64'd1 << count) < 64'(width) + 64'(count) + 1) count++;

        return count;
    endfunction

    // SECDED stripes contain at most 256 data bits and 266 stored bits.
    // Modes 0 and 1 store plain data and data with one parity bit, respectively.
    function automatic int code_width(input int width, input int protection);
        int stripes;
        int last;
        stripes = (width + 255) / 256;
        last = width - (stripes - 1) * 256;

        return protection == 2 ?
            (stripes - 1) * 266 + last + hamming_bits(last) + 1 : width + protection;
    endfunction

    // Conceptual Hamming positions are one-based; powers of two carry parity.
    function automatic int unsigned data_index(input int unsigned position);
        int unsigned index;
        index = 0;

        for (int unsigned lower = 1; lower < position; lower++)
            if ((lower & (lower - 1)) != 0) index++;

        return index;
    endfunction
endpackage
