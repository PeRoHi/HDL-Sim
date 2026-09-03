module priority_enc (
    input wire [3:0] req,
    output reg [1:0] grant,
    output reg valid
);
    always @(*) begin
        valid = 1;
        // casexによる優先度付きエンコーダ
        casex (req)
            4'b1xxx: grant = 2'd3;
            4'b01xx: grant = 2'd2;
            4'b001x: grant = 2'd1;
            4'b0001: grant = 2'd0;
            default: begin
                grant = 2'd0;
                valid = 0;
            end
        endcase
    end
endmodule
