// lfsr_8bit.v
module lfsr_8bit (
    input wire clk,
    input wire rst_n,
    output reg [7:0] rand_out
);
    wire feedback;
    // 多項式: x^8 + x^6 + x^5 + x^4 + 1
    assign feedback = rand_out[7] ^ rand_out[5] ^ rand_out[4] ^ rand_out[3];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rand_out <= 8'h01; // ゼロにしないこと
        end else begin
            rand_out <= {rand_out[6:0], feedback};
        end
    end
endmodule