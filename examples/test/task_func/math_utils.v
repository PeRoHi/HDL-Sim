module math_utils (
    input wire [3:0] a,
    output reg [15:0] fact_out,
    output reg [2:0] pop_out
);
    // functionのテスト (内部にintegerとforループを持つ)
    function [15:0] factorial;
        input [3:0] n;
        integer i;
        begin
            factorial = 1;
            for (i = 1; i <= n; i = i + 1) begin
                factorial = factorial * i;
            end
        end
    endfunction

    // taskのテスト (出力ポートを持つ)
    task popcount;
        input [3:0] val;
        output [2:0] count;
        integer i;
        begin
            count = 0;
            for (i = 0; i < 4; i = i + 1) begin
                if (val[i]) count = count + 1;
            end
        end
    endtask

    always @(*) begin
        fact_out = factorial(a);
        popcount(a, pop_out);
    end
endmodule
