module tb_multi;
  reg ra;
  reg rb;
  wire ry;

  and2 u_and (.a(ra), .b(rb), .y(ry));

  initial begin
    ra = 0;
    rb = 0;
    $display("start ra=%d rb=%d", ra, rb);
    #1 ra = 1;
    #1 rb = 1;
    $display("done ry=%d", ry);
  end
endmodule
