/* File name 4add.v */
/* 4-bit adder */ 
module add_00( a , b , c ); 
input[3:0]a,b;
output[4:0]c;
 assign c=a+b;
endmodule 