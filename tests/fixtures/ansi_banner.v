// ---------------------------------------------------------------
// A banner comment in front of the module. The header has to be found
// after it, and the body sliced from the end of the header rather than
// from len(header), or it lands in the middle of this comment.
// ---------------------------------------------------------------
`timescale 1ns/1ps

module ansi_top #(
    // ---- sizes ----
    parameter DATA_W = 64,           // data width in bits
    parameter ID_W   = 4,
    parameter [7:0] MAGIC = 8'hA5
) (
    input  wire              clk,
    input  wire              rst,

    // ---- AXI write ----
    input  wire [DATA_W-1:0] s_axi_wdata,
    input  wire              s_axi_wvalid,
    output wire              s_axi_wready,

    // -------------------------------------------------
    // Status
    // -------------------------------------------------
    output reg  [7:0]        count = 8'd0,   // the initialiser is not part of the name
    output wire              busy, done,

    // -------------------------------------------------
    //---------- Debug ports ----------------------------
    // -------------------------------------------------
    output wire [3:0]        dbg
);

localparam DEPTH = 16;
localparam [3:0] MODE = 4'd2;

/* looks like an instantiation, but it is a comment: fake_mod u_fake (a, b); */
wire [DATA_W-1:0] q;
reg  [7:0] msg = "child_z u_z (";

child_a u_a (.clk(clk));

child_b #(.W(DATA_W)) u_b (.clk(clk));

child_c #(
    .A(1),
    .B(2)
) u_c (.clk(clk));

child_d u_d [3:0] (.clk(clk));

and g0 (q[0], clk, rst);        // a gate primitive, not a module

initial begin
    do_something (clk, rst);    // a task call has no instance name
end

always @(posedge clk) begin
    if (rst)
        count <= 8'd0;
    else
        count <= count + 8'd1;
end

endmodule

module second_module (input wire a);
    should_not_appear u_x (.a(a));
    localparam NOT_MINE = 1;
endmodule
