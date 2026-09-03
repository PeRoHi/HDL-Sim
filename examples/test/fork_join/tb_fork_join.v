`timescale 1ns/1ns
module tb_fork_join;
    reg a, b, c;

    initial begin
        a = 0; b = 0; c = 0;
        
        $display("[%0t] Start fork-join", $time);
        fork
            #30 a = 1;
            #10 b = 1;
            #20 c = 1;
        join
        $display("[%0t] End fork-join. a=%b, b=%b, c=%b", $time, a, b, c);
        
        #10 $finish;
    end
endmodule
