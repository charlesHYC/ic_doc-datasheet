// ---------------------------------------------------------------
// soc_app_top - stub for the ic-datasheet worked example.
// The framework application shell the design lives in. Its port list
// belongs to the framework, which is why the datasheet omits its pin
// table and documents the register map instead.
// ---------------------------------------------------------------
module soc_app_top #(
    parameter CH              = 16,     // memory channels
    parameter MEM_ADDR_W      = 33,     // memory address width
    parameter MEM_DATA_W      = 256,    // memory data width
    parameter MEM_ID_W        = 6,      // memory AXI ID width
    parameter HOST_ADDR_W     = 64,     // host address width
    parameter CSR_ADDR_W      = 16,     // register window address width
    parameter STREAM_W        = 512,    // TX stream width
    parameter PORTS           = 1       // network ports
) (
    input  wire                        clk,
    input  wire                        rst,

    // ---- register window, AXI-Lite ----
    input  wire [CSR_ADDR_W-1:0]       s_axil_awaddr,
    input  wire                        s_axil_awvalid,
    output wire                        s_axil_awready,
    input  wire [31:0]                 s_axil_wdata,
    input  wire                        s_axil_wvalid,
    output wire                        s_axil_wready,
    output wire                        s_axil_bvalid,
    input  wire                        s_axil_bready,
    input  wire [CSR_ADDR_W-1:0]       s_axil_araddr,
    input  wire                        s_axil_arvalid,
    output wire                        s_axil_arready,
    output wire [31:0]                 s_axil_rdata,
    output wire                        s_axil_rvalid,
    input  wire                        s_axil_rready,

    // ---- host DMA read request ----
    output wire [HOST_ADDR_W-1:0]      m_dma_addr,
    output wire [31:0]                 m_dma_len,
    output wire                        m_dma_valid,
    input  wire                        m_dma_ready,
    input  wire                        s_dma_done,

    // ---- memory, one AXI port per channel ----
    output wire [CH*MEM_ADDR_W-1:0]    m_axi_awaddr,
    output wire [CH-1:0]               m_axi_awvalid,
    input  wire [CH-1:0]               m_axi_awready,
    output wire [CH*MEM_DATA_W-1:0]    m_axi_wdata,
    output wire [CH-1:0]               m_axi_wvalid,
    input  wire [CH-1:0]               m_axi_wready,
    input  wire [CH-1:0]               m_axi_bvalid,
    output wire [CH-1:0]               m_axi_bready,
    output wire [CH*MEM_ADDR_W-1:0]    m_axi_araddr,
    output wire [CH-1:0]               m_axi_arvalid,
    input  wire [CH-1:0]               m_axi_arready,
    input  wire [CH*MEM_DATA_W-1:0]    m_axi_rdata,
    input  wire [CH-1:0]               m_axi_rvalid,
    output wire [CH-1:0]               m_axi_rready,

    // ---- TX stream, port 0 is taken over during a replay ----
    input  wire [PORTS*STREAM_W-1:0]   s_axis_tx_tdata,
    input  wire [PORTS-1:0]            s_axis_tx_tvalid,
    output wire [PORTS-1:0]            s_axis_tx_tready,
    output wire [PORTS*STREAM_W-1:0]   m_axis_tx_tdata,
    output wire [PORTS-1:0]            m_axis_tx_tvalid,
    input  wire [PORTS-1:0]            m_axis_tx_tready
);

write_path #(.CH(CH)) u_wr (.clk(clk), .rst(rst));

read_path #(.CH(CH)) u_rd (.clk(clk), .rst(rst));

genvar c;
generate
    for (c = 0; c < CH; c = c + 1) begin : g_slice
        axi_reg_wr #(.DATA_WIDTH(MEM_DATA_W)) u_slice_wr (.clk(clk), .rst(rst));
        axi_reg_rd #(.DATA_WIDTH(MEM_DATA_W)) u_slice_rd (.clk(clk), .rst(rst));
    end
endgenerate

endmodule
