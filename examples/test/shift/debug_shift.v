module debug_shift (
    input wire clk,
    input wire rst_n,
    input wire shift_en,
    input wire din,
    output reg [3:0] q
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q <= 4'b0000;
        end else if (shift_en) begin
            q <= {q[2:0], din};
        end
    end
endmodule
