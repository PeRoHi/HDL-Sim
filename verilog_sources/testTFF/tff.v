module TFF (R, T, Q, QB);
input R, T;
output Q, QB; 
reg Q;

assign QB= ~Q;
always @(   posedge R or posedge T)
      Q <= ( R )?    0 :   ~Q  ;  
endmodule
