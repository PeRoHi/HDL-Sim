// main_controller.v
module main_controller (
    input wire clk,
    input wire rst_n,
    input wire btn_start,
    input wire btn_stop,
    input wire [7:0] random_val,
    output reg led,
    output reg timer_en,
    output reg timer_rst
);
    localparam IDLE = 2'd0;
    localparam WAIT = 2'd1;
    localparam MEASURE = 2'd2;
    localparam DONE = 2'd3;

    reg [1:0] state, next_state;
    reg [7:0] wait_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else state <= next_state;
    end

    always @(*) begin
        next_state = state;
        case (state)
            IDLE: if (btn_start) next_state = WAIT;
            WAIT: if (btn_stop) next_state = DONE; // フライング
                  else if (wait_cnt == 0) next_state = MEASURE;
            MEASURE: if (btn_stop) next_state = DONE;
            DONE: if (btn_start) next_state = IDLE;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wait_cnt <= 0;
            led <= 0;
            timer_en <= 0;
            timer_rst <= 1;
        end else begin
            case (state)
                IDLE: begin
                    wait_cnt <= random_val + 8'd50; // 最小待機時間を確保
                    led <= 0;
                    timer_en <= 0;
                    timer_rst <= 1;
                end
                WAIT: begin
                    if (wait_cnt > 0) wait_cnt <= wait_cnt - 1;
                    timer_rst <= 0;
                end
                MEASURE: begin
                    led <= 1;
                    timer_en <= 1;
                end
                DONE: begin
                    led <= 0;
                    timer_en <= 0;
                end
            endcase
        end
    end
endmodule