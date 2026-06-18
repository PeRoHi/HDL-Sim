`timescale 1ns/1ns       
module TFF_tp;
reg   R, T;  
wire  Q, QB;       

parameter STEP = 50;   
TFF  TFF(R, T, Q, QB);  

initial begin
	              R = 0;  T= 0;
	#(STEP/4)     R = 1;
	#(STEP/6)     R = 0;
     #(STEP/2)       T=1 ;
	#(STEP/4)     T = 0;
     #(STEP/2)     T=1 ;
	#(STEP/2)      T = 0;
	#(STEP/4)    $finish;
	
end
endmodule