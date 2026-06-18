module sai_test; 
  reg ck, reset, enable; 
  wire [6:0] lamp; 
  parameter STEP = 1000; 
  sai sai( ck, reset, enable, lamp ); 
initial ck=0;
always#(STEP/2)
   ck = ~ck;
initial begin
		reset = 0; enable = 0;
   #STEP 	reset = 1; 
   #STEP 	reset = 0; 
   #STEP	enable = 1;
   #(STEP*5) 	enable = 0;
   #STEP 	enable = 1;  
   #(STEP*5) $finish;
end 
initial $monitor( $stime, " reset= %b enable= %b saikoro= %h lamp=%b", reset, enable, sai.cnt, lamp); 
endmodule 