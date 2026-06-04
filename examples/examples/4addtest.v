/* Top module name: 4addtst.v */
/* Test module for 4add.v, */ 
`timescale 1ps/1ps /* Unit timescale = 1ps */ 
 module mul_ts; 
  reg [3:0] a , b; /* Input signal */
  wire [4:0] c; /* Output signal */ 
  add_00 add_00( a, b, c ); /* Call module */ 
      parameter STEP = 1000; /* 1STEP = 1ps * 1000 = 1ns */ 
 initial begin

    a = 4'h0; b = 4'h0; /* TIME = 0 nsec */
   #STEP a = 4'h5; b = 4'h5; /* TIME = 1 nsec */
   #STEP a = 4'hf; b = 4'hf; /* TIME = 2 nsec */
   #STEP a = 4'h1; b = 4'h2; /* TIME = 3 nsec */
   #STEP a = 4'h3; b = 4'h2; /* TIME = 4 nsec */
   #STEP $finish;

end 
initial $monitor( $stime, "a = %h b = %h c = %h", a, b, c ); 
 endmodule 