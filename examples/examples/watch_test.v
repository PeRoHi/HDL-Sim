`timescale 1ns/1ns       
module DFF_tp;
reg   ck, sysreset, SW1, SW2, SW3;
wire  sec_reset, min_inc, hour_inc, sec_onoff, min_onoff, hour_onoff;

parameter STEP = 50;   
state_dec  state_dec(ck, sysreset, SW1, SW2, SW3, sec_reset, min_inc, hour_inc, sec_onoff, min_onoff, hour_onoff);

always #(STEP/2)	ck = ~ck;    //　クロック作成
initial begin
	              sysreset = 1;  SW1=0; SW2=0; SW3=0; ck = 0;
	#(STEP)     sysreset = 0; SW2 = 1;
	#(STEP)     SW2 = 0;
	#(STEP)     SW3 = 1;
	#(STEP)     SW3 = 0;
	#(STEP)     SW3 = 1;
	#(STEP)     SW3 = 0;
	#(STEP)     SW1 = 1;
	#(STEP)     SW1 = 0;
	#(STEP)     SW2 = 1;
	#(STEP)     SW2 = 0;
     	#(STEP*4)    $finish;
	
end
endmodule
