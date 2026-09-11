// ---------------------------------------------------------------
// dma_engine - stub for the ic-datasheet worked example.
// Moves data from host memory into on-card memory: takes a copy
// descriptor, returns a status pulse.
// ---------------------------------------------------------------
module dma_engine #(
    parameter HOST_ADDR_W = 64,     // host address width
    parameter MEM_ADDR_W  = 33,     // flat on-card memory address
    parameter LEN_W       = 32,     // transfer length width
    parameter TAG_W       = 8,      // descriptor tag width
    parameter SEGS        = 2,      // staging RAM segments
    parameter SEG_DATA_W  = 512,    // bits per segment
    parameter SEG_ADDR_W  = 11,     // words per segment, as an address width
    parameter CH          = 16,     // memory channels
    parameter DATA_W      = 256,    // memory data width
    parameter SLOTS       = 32      // batches in flight
) (
    input  wire                     clk,
    input  wire                     rst,

    // ---- copy descriptor in ----
    input  wire [HOST_ADDR_W-1:0]   s_desc_host_addr,
    input  wire [MEM_ADDR_W-1:0]    s_desc_mem_addr,
    input  wire [LEN_W-1:0]         s_desc_len,
    input  wire [TAG_W-1:0]         s_desc_tag,
    input  wire                     s_desc_valid,
    output wire                     s_desc_ready,

    // ---- status out ----
    output wire [TAG_W-1:0]         m_status_tag,
    output wire                     m_status_error,
    output wire                     m_status_valid,

    // ---- staging RAM write port, driven by the framework DMA ----
    input  wire [SEGS*SEG_ADDR_W-1:0] ram_wr_addr,
    input  wire [SEGS*SEG_DATA_W-1:0] ram_wr_data,
    input  wire [SEGS-1:0]            ram_wr_en,

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
    output wire [CH-1:0]            m_axi_bready,

    output wire [5:0]               dbg_stall     // per-source stall flags
);

localparam BATCH_BYTES = 512;
localparam WIDE_W      = SEGS * SEG_DATA_W / 2;

stage_ram #(.SEGS(SEGS), .SEG_DATA_W(SEG_DATA_W)) u_ram (.clk(clk));

axi_wr_master #(.DATA_W(WIDE_W)) u_wr (.clk(clk), .rst(rst));

axi_demux #(.CH(CH), .DATA_W(WIDE_W)) u_demux (.clk(clk), .rst(rst));

genvar c;
generate
    for (c = 0; c < CH; c = c + 1) begin : g_ch
        axi_downsize #(.S_DATA_W(WIDE_W), .M_DATA_W(DATA_W)) u_down (.clk(clk), .rst(rst));
    end
endgenerate

endmodule
