// ---------------------------------------------------------------
// axi_demux - stub for the ic-datasheet worked example.
// Routes one wide AXI write master to CH channel-local masters. The
// channel is a slice of the address, so there is no decode table.
// ---------------------------------------------------------------
module axi_demux #(
    parameter CH        = 16,       // output channels
    parameter ADDR_W    = 33,       // address width
    parameter DATA_W    = 512,      // data width, both sides
    parameter ID_W      = 8,        // AXI ID width
    parameter CH_OFFSET = 9         // lowest address bit of the channel field
) (
    input  wire                   clk,
    input  wire                   rst,

    // ---- AXI write slave ----
    input  wire [ID_W-1:0]        s_axi_awid,
    input  wire [ADDR_W-1:0]      s_axi_awaddr,
    input  wire [7:0]             s_axi_awlen,
    input  wire                   s_axi_awvalid,
    output wire                   s_axi_awready,
    input  wire [DATA_W-1:0]      s_axi_wdata,
    input  wire [DATA_W/8-1:0]    s_axi_wstrb,
    input  wire                   s_axi_wlast,
    input  wire                   s_axi_wvalid,
    output wire                   s_axi_wready,
    output wire [ID_W-1:0]        s_axi_bid,
    output wire                   s_axi_bvalid,
    input  wire                   s_axi_bready,

    // ---- AXI write masters, one per channel ----
    output wire [CH*ADDR_W-1:0]   m_axi_awaddr,
    output wire [CH*8-1:0]        m_axi_awlen,
    output wire [CH-1:0]          m_axi_awvalid,
    input  wire [CH-1:0]          m_axi_awready,
    output wire [CH*DATA_W-1:0]   m_axi_wdata,
    output wire [CH-1:0]          m_axi_wlast,
    output wire [CH-1:0]          m_axi_wvalid,
    input  wire [CH-1:0]          m_axi_wready,
    input  wire [CH-1:0]          m_axi_bvalid,
    output wire [CH-1:0]          m_axi_bready
);

localparam CH_BITS = $clog2(CH);

endmodule
