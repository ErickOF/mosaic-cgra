`timescale 1ns / 1ps
// GENERATED canonical MMIO byte offsets.
package system_registers_pkg;
    typedef enum logic [31:0] {
        SYS_REG_IDENTITY = 32'h0000,
        SYS_REG_VERSION = 32'h0004,
        SYS_REG_GEOMETRY = 32'h0008,
        SYS_REG_QUEUES = 32'h000c,
        SYS_REG_STATUS = 32'h0010,
        SYS_REG_STATE = 32'h0014,
        SYS_REG_SYSTEM_HASH = 32'h0040,
        SYS_REG_ARRAY_HASH = 32'h0060,
        SYS_REG_PROGRAM_BUFFER = 32'h1000,
        SYS_REG_PROGRAM_OFFSET = 32'h1004,
        SYS_REG_PROGRAM_COUNT_GENERATION = 32'h1008,
        SYS_REG_PROGRAM_DOORBELL = 32'h100c,
        SYS_REG_NATIVE_EPOCHS = 32'h2000,
        SYS_REG_NATIVE_GENERATIONS = 32'h2004,
        SYS_REG_SCRATCHPAD_GENERATIONS = 32'h2008,
        SYS_REG_PROGRAM_STATUS = 32'h1010,
        SYS_REG_PROGRAM_DISCARD = 32'h1018,
        SYS_REG_PROGRAM_RESULT = 32'h101c,
        SYS_REG_PROGRAM_CANCEL = 32'h1020,
        SYS_REG_BUFFER_INDEX = 32'h3000,
        SYS_REG_BUFFER_BASE_LO = 32'h3004,
        SYS_REG_BUFFER_BASE_HI = 32'h3008,
        SYS_REG_BUFFER_SIZE = 32'h300c,
        SYS_REG_BUFFER_OWNER_KERNEL = 32'h3010,
        SYS_REG_BUFFER_GENERATION_PERMISSIONS = 32'h3014,
        SYS_REG_BUFFER_COMMIT = 32'h3020,
        SYS_REG_BUFFER_DISCARD = 32'h3024,
        SYS_REG_BUFFER_STATUS = 32'h3028,
        SYS_REG_BUFFER_FENCE = 32'h3040,
        SYS_REG_INTERRUPT_MASK = 32'h4000,
        SYS_REG_EVENT_COUNT = 32'h4004,
        SYS_REG_INTERRUPT_STATUS = 32'h4008,
        SYS_REG_EVENT_ACK = 32'h4020,
        SYS_REG_EVENT_HEAD = 32'h4040,
        SYS_REG_COUNTER_SNAPSHOT = 32'h5000,
        SYS_REG_COUNTER_VALID = 32'h5004,
        SYS_REG_COUNTERS = 32'h5010,
        SYS_REG_FIRST_ERROR = 32'h7000,
        SYS_REG_ERROR_CLEAR = 32'h7004,
        SYS_REG_DRAIN = 32'h7008,
        SYS_REG_ERROR_ADDRESS_LO = 32'h7010,
        SYS_REG_ERROR_ADDRESS_HI = 32'h7014,
        SYS_REG_ERROR_IDENTITY = 32'h7018,
        SYS_REG_LAST_ARRAY_RESPONSE = 32'h7100
    } system_register_t;
    function automatic logic system_register_readonly(input logic [31:0] address);
        system_register_readonly = 1'b0;
        if (address >= SYS_REG_IDENTITY &&
            address < SYS_REG_IDENTITY + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_VERSION &&
            address < SYS_REG_VERSION + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_GEOMETRY &&
            address < SYS_REG_GEOMETRY + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_QUEUES &&
            address < SYS_REG_QUEUES + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_STATUS &&
            address < SYS_REG_STATUS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_STATE &&
            address < SYS_REG_STATE + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_SYSTEM_HASH &&
            address < SYS_REG_SYSTEM_HASH + 32'd32)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_ARRAY_HASH &&
            address < SYS_REG_ARRAY_HASH + 32'd32)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_NATIVE_EPOCHS &&
            address < SYS_REG_NATIVE_EPOCHS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_NATIVE_GENERATIONS &&
            address < SYS_REG_NATIVE_GENERATIONS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_SCRATCHPAD_GENERATIONS &&
            address < SYS_REG_SCRATCHPAD_GENERATIONS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_PROGRAM_STATUS &&
            address < SYS_REG_PROGRAM_STATUS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_PROGRAM_RESULT &&
            address < SYS_REG_PROGRAM_RESULT + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_BUFFER_STATUS &&
            address < SYS_REG_BUFFER_STATUS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_EVENT_COUNT &&
            address < SYS_REG_EVENT_COUNT + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_INTERRUPT_STATUS &&
            address < SYS_REG_INTERRUPT_STATUS + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_EVENT_HEAD &&
            address < SYS_REG_EVENT_HEAD + 32'd64)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_COUNTER_VALID &&
            address < SYS_REG_COUNTER_VALID + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_COUNTERS &&
            address < SYS_REG_COUNTERS + 32'd32)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_FIRST_ERROR &&
            address < SYS_REG_FIRST_ERROR + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_ERROR_ADDRESS_LO &&
            address < SYS_REG_ERROR_ADDRESS_LO + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_ERROR_ADDRESS_HI &&
            address < SYS_REG_ERROR_ADDRESS_HI + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_ERROR_IDENTITY &&
            address < SYS_REG_ERROR_IDENTITY + 32'd4)
            system_register_readonly = 1'b1;
        if (address >= SYS_REG_LAST_ARRAY_RESPONSE &&
            address < SYS_REG_LAST_ARRAY_RESPONSE + 32'd128)
            system_register_readonly = 1'b1;
    endfunction
endpackage
