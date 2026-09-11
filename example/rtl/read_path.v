// ---------------------------------------------------------------
// read_path - stub for the ic-datasheet worked example.
// Reads stored records back out of on-card memory and turns them into
// an output stream. Only the interface matters here: the body is empty
// apart from the instantiations the hierarchy is read from.
// ---------------------------------------------------------------
module read_path #(
    parameter CH        = 16,       // memory channels
    parameter LANES     = 8,        // read masters; must divide CH
    parameter ADDR_W    = 33,       // memory address width
    parameter DATA_W    = 256,      // memory data width
    parameter ID_W      = 6,        // AXI ID width
    parameter STREAM_W  = 512,      // output stream width
    parameter CAP_DEPTH = 1024      // readback capture depth, in records
) (
    input  wire                   clk,
    input  wire                   rst,

    // ---- control ----
    input  wire                   go,           // start a run, one-cycle pulse
    input  wire [31:0]            total,        // records to replay
    input  wire                   free_run,     // ignore timestamps and send back to back
    output reg                    busy,
    output reg                    done,         // one-cycle pulse at the end of a run
    output wire [31:0]            run_cycles,   // clock cycles the last run took

    // ---- memory read, one port per channel ----
    output wire [CH*ID_W-1:0]     m_axi_arid,
    output wire [CH*ADDR_W-1:0]   m_axi_araddr,
    output wire [CH*8-1:0]        m_axi_arlen,
    output wire [CH-1:0]          m_axi_arvalid,
    input  wire [CH-1:0]          m_axi_arready,
    input  wire [CH*DATA_W-1:0]   m_axi_rdata,
    input  wire [CH-1:0]          m_axi_rlast,
    input  wire [CH-1:0]          m_axi_rvalid,
    output wire [CH-1:0]          m_axi_rready,

    // ---- output stream ----
    output wire [STREAM_W-1:0]    m_axis_tdata,
    output wire [STREAM_W/8-1:0]  m_axis_tkeep,
    output wire                   m_axis_tvalid,
    input  wire                   m_axis_tready,
    output wire                   m_axis_tlast
);

localparam LANE_BITS = $clog2(LANES);
localparam BEATS     = 16;          // beats per 512 B batch

genvar g;
generate
    for (g = 0; g < LANES; g = g + 1) begin : g_lane
        axis_fifo #(.DATA_WIDTH(2*DATA_W), .DEPTH(2048)) u_fifo (.clk(clk), .rst(rst));
    end
endgenerate

endmodule
