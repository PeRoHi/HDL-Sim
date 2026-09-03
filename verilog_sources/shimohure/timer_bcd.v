// timer_bcd.v
module timer_bcd (
    input wire clk,
    input wire rst_n,
    input wire en,
    input wire clr,
    output reg [3:0] bcd0,
    output reg [3:0] bcd1,
    output reg [3:0] bcd2,
    output reg [3:0] bcd3
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bcd0 <= 0; bcd1 <= 0; bcd2 <= 0; bcd3 <= 0;
        end else if (clr) begin
            bcd0 <= 0; bcd1 <= 0; bcd2 <= 0; bcd3 <= 0;
        end else if (en) begin
            if (bcd0 == 9) begin
                bcd0 <= 0;
                if (bcd1 == 9) begin
                    bcd1 <= 0;
                    if (bcd2 == 9) begin
                        bcd2 <= 0;
                        if (bcd3 == 9) bcd3 <= 0;
                        else bcd3 <= bcd3 + 1;
                    end else begin
                        bcd2 <= bcd2 + 1;
                    end
                end else begin
                    bcd1 <= bcd1 + 1;
                end
            end else begin
                bcd0 <= bcd0 + 1;
            end
        end
    end
endmodule