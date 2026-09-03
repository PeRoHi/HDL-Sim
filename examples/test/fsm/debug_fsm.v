module debug_fsm (
    input wire clk,
    input wire rst_n,
    input wire din,
    output reg detected
);
    localparam S_IDLE = 3'd0;
    localparam S_1    = 3'd1;
    localparam S_11   = 3'd2;
    localparam S_110  = 3'd3;

    reg [2:0] state;

    // Detects sequence "1101"
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            detected <= 0;
        end else begin
            detected <= 0;
            case (state)
                S_IDLE: if (din) state <= S_1;
                S_1:    if (din) state <= S_11; else state <= S_IDLE;
                S_11:   if (!din) state <= S_110;
                S_110:  begin
                            if (din) begin
                                state <= S_1;
                                detected <= 1;
                            end else begin
                                state <= S_IDLE;
                            end
                        end
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
