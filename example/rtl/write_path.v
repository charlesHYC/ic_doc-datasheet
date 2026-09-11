// ---------------------------------------------------------------
// write_path - stub for the ic-datasheet worked example.
// The register face of the write side: control and status, and the
// hand-off to the engine that moves the data.
// ---------------------------------------------------------------
module write_path #(
    parameter HOST_ADDR_W = 64,     // host address width
    parameter MEM_ADDR_W  = 33,     // flat on-card memory address
    parameter LEN_W       = 32,     // transfer length width
    parameter CH          = 16,     // memory channels
    parameter DATA_W      = 256     // memory data width
) (
    input  wire                     clk,
    input  wire                     rst,

    // ---- registers ----
    input  wire [HOST_ADDR_W-1:0]   src_addr,     // host address of the first record
    input  wire [LEN_W-1:0]         length,       // bytes to move
    input  wire                     go,           // start, one-cycle pulse
    input  wire                     desc_mode,    // take segments from the descriptor queue
    output wire                     busy,
    output wire                     done,         // one-cycle pulse
    output wire [5:0]               debug_state,  // per-source stall flags

    // ---- host read request to the framework DMA ----
    output wire [HOST_ADDR_W-1:0]   m_dma_addr,
    output wire [LEN_W-1:0]         m_dma_len,
    output wire                     m_dma_valid,
    input  wire                     m_dma_ready,
    input  wire                     s_dma_done,

    // ---- memory write, one port per channel ----
    output wire [CH*MEM_ADDR_W-1:0] m_axi_awaddr,
    output wire [CH*8-1:0]          m_axi_awlen,
    output wire [CH-1:0]            m_axi_awvalid,
    input  wire [CH-1:0]            m_axi_awready,
    output wire [CH*DATA_W-1:0]     m_axi_wdata,
    output wire [CH-1:0]            m_axi_wlast,
    output wire [CH-1:0]            m_axi_wvalid,
    input  wire [CH-1:0]            m_axi_wready,
    input  wire [CH-1:0]            m_axi_bvalid,
    output wire [CH-1:0]            m_axi_bready
);

dma_engine #(.HOST_ADDR_W(HOST_ADDR_W), .MEM_ADDR_W(MEM_ADDR_W), .CH(CH)) u_engine (
    .clk(clk), .rst(rst));

endmodule
