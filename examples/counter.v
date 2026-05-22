// 4-bit counter with clock and non-blocking updates
module counter;
  reg clk;
  reg [3:0] count;

  initial begin
    clk = 0;
    count = 0;
    forever #5 clk = ~clk;
  end

  always @(posedge clk) begin
    count <= count + 1;
  end
endmodule
