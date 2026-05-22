// Hierarchical design: and2 gate instanced in testbench
module and2(input a, input b, output y);
  assign y = a & b;
endmodule

module tb;
  reg ra;
  reg rb;
  wire ry;

  and2 u_and (.a(ra), .b(rb), .y(ry));

  initial begin
    ra = 0;
    rb = 0;
    #1 ra = 1;
    #1 rb = 1;
    #1 ra = 0;
  end
endmodule
