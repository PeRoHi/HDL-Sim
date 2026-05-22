// Parameterized counter width
module param_counter;
  parameter WIDTH = 4;
  reg clk;
  reg [WIDTH-1:0] count;

  initial begin
    clk = 0;
    count = 0;
    forever #5 clk = ~clk;
  end

  always @(posedge clk) begin
    count <= count + 1;
  end
endmodule
