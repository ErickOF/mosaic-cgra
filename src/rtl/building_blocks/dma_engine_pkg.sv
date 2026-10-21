`timescale 1ns / 1ps

// Repository-local DMA encodings. Memory-space and stream identifiers are
// opaque values; an external platform contract must map these enums explicitly.
package dma_engine_pkg;
    typedef enum logic [1:0] {
        DMA_MEMORY_TO_MEMORY = 2'd0,
        DMA_MEMORY_TO_STREAM = 2'd1,
        DMA_STREAM_TO_MEMORY = 2'd2
    } dma_transfer_t;

    typedef enum logic [1:0] {
        DMA_START_IMMEDIATE = 2'd0,
        DMA_START_EVENT_OR  = 2'd1,
        DMA_START_EVENT_AND = 2'd2
    } dma_start_t;

    typedef enum logic [1:0] {
        DMA_SUCCESS = 2'd0,
        DMA_ERROR = 2'd1,
        DMA_CANCELED = 2'd2,
        DMA_FLUSHED = 2'd3
    } dma_status_t;

    typedef enum logic [4:0] {
        DMA_ERR_NONE = 5'd0,
        DMA_ERR_COMMAND = 5'd1,
        DMA_ERR_REGION = 5'd2,
        DMA_ERR_PROTOCOL = 5'd3,
        DMA_ERR_DUPLICATE = 5'd4,
        DMA_ERR_ALIGNMENT = 5'd5,
        DMA_ERR_BOUNDS = 5'd6,
        DMA_ERR_PERMISSION = 5'd7,
        DMA_ERR_EVENT = 5'd8,
        DMA_ERR_BURST = 5'd9,
        DMA_ERR_OVERLAP = 5'd10,
        DMA_ERR_PARITY = 5'd11,
        DMA_ERR_FRAMING = 5'd12,
        DMA_ERR_SOURCE = 5'd13,
        DMA_ERR_WRITE = 5'd14,
        DMA_ERR_BACKEND = 5'd15,
        DMA_ERR_EPOCH = 5'd16,
        DMA_ERR_TIMEOUT = 5'd17,
        DMA_ERR_CANCELED = 5'd18,
        DMA_ERR_CANCEL_TIMEOUT = 5'd19,
        DMA_ERR_FLUSH = 5'd20,
        DMA_ERR_OVERFLOW = 5'd21,
        DMA_ERR_UNKNOWN = 5'd22
    } dma_error_t;

    typedef enum logic [2:0] {
        DMA_IDLE = 3'd0,
        DMA_ARM_STORE = 3'd1,
        DMA_ARM_LOAD = 3'd2,
        DMA_RUN = 3'd3,
        DMA_CANCEL = 3'd4,
        DMA_COMPLETE = 3'd5,
        DMA_FATAL = 3'd6
    } dma_phase_t;
endpackage
