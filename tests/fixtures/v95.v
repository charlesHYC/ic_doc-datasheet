// A Verilog-95 header, the form memory compilers and vendor macros emit:
// bare names in the header, directions and widths declared in the body.
module v95_mem (Q, CLK, CEN, WEN, A, D);
parameter WORDS = 256;
parameter BITS  = 128;
output [BITS-1:0] Q;          // read data
input CLK;
input CEN, WEN;               // two names in one declaration
input [7:0] A;
input [BITS-1:0] D;

reg [BITS-1:0] mem [0:WORDS-1];

task load;
    input [7:0] addr;         // a task input, not a port
    begin end
endtask

endmodule
