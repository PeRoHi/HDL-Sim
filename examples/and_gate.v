// Combinational AND gate
module and_gate;
  wire a;
  wire b;
  wire y;

  reg ra;
  reg rb;

  assign a = ra;
  assign b = rb;
  assign y = a & b;

  initial begin
    ra = 0;
    rb = 0;
    #1 ra = 1;
    #1 rb = 1;
    #1 ra = 0;
  end
endmodule
