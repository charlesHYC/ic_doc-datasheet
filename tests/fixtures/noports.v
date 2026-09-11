// A module with no port list at all, the shape of a testbench top.
module tb_top;
parameter N = 4;
localparam M = N * 2;

dut #(.N(N)) u_dut ();

endmodule
