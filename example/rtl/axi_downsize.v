// ---------------------------------------------------------------
// axi_downsize - stub for the ic-datasheet worked example.
// Converts an AXI write channel to a narrower one: each wide beat is
// sent as RATIO narrow beats, and the burst length scaled to match.
// ---------------------------------------------------------------
module axi_downsize #(
    parameter ADDR_W   = 33,        // address width
    parameter S_DATA_W = 512,       // slave (wide) data width
    parameter M_DATA_W = 256,       // master (narrow) data width
    parameter ID_W     = 8          // AXI ID width
) (
    input  wire                    clk,
    input  wire                    rst,

    // ---- AXI write slave, wide ----
    input  wire [ADDR_W-1:0]       s_axi_awaddr,
    input  wire [7:0]              s_axi_awlen,
    input  wire                    s_axi_awvalid,
    output wire                    s_axi_awready,
    input  wire [S_DATA_W-1:0]     s_axi_wdata,
    input  wire                    s_axi_wlast,
    input  wire                    s_axi_wvalid,
    output wire                    s_axi_wready,
    output wire                    s_axi_bvalid,
    input  wire                    s_axi_bready,

    // ---- AXI write master, narrow ----
    output wire [ADDR_W-1:0]       m_axi_awaddr,
    output wire [7:0]              m_axi_awlen,
    output wire                    m_axi_awvalid,
    input  wire                    m_axi_awready,
    output wire [M_DATA_W-1:0]     m_axi_wdata,
    output wire                    m_axi_wlast,
    output wire                    m_axi_wvalid,
    input  wire                    m_axi_wready,
    input  wire                    m_axi_bvalid,
    output wire                    m_axi_bready
);

localparam RATIO = S_DATA_W / M_DATA_W;

endmodule
