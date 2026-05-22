// Clock fragment for include demo
initial begin
  clk = 0;
  forever #5 clk = ~clk;
end
