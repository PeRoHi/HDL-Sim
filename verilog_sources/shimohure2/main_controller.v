module main_controller(CLK, RST, START_BTN, STOP_BTN, RAND_VAL, TIMER_VAL, LED_TARGET, LED_FOUL, TIMER_EN, TIMER_RST);
    input CLK, RST, START_BTN, STOP_BTN;
    input [7:0] RAND_VAL;
    input [15:0] TIMER_VAL;
    output LED_TARGET, LED_FOUL, TIMER_EN, TIMER_RST;
    reg LED_TARGET, LED_FOUL, TIMER_EN, TIMER_RST;
    
    reg [1:0] cur, nxt;
    reg [7:0] wait_time;

    parameter IDLE = 2'b00, WAIT_STATE = 2'b01, MEASURE = 2'b10, RESULT = 2'b11;

    // ��ԑJ�� (P.116)
    always @(posedge CLK or posedge RST) begin
        if (RST) cur <= IDLE;
        else cur <= nxt;
    end

    // ����Ԍ��� (P.117)
    always @(cur or START_BTN or STOP_BTN or TIMER_VAL or wait_time) begin
        nxt = cur;
        case (cur)
            IDLE: if (START_BTN) nxt = WAIT_STATE;
            WAIT_STATE: begin
                if (STOP_BTN) nxt = RESULT; 
                else if (TIMER_VAL[7:0] >= wait_time) nxt = MEASURE;
            end
            MEASURE: if (STOP_BTN) nxt = RESULT;
            RESULT: if (START_BTN) nxt = IDLE;
        endcase
    end

   // �o�͐��� (P.118)
    always @(posedge CLK) begin
        LED_TARGET <= 1'b0; 
        TIMER_EN <= 1'b0; 
        TIMER_RST <= 1'b0;

        case (cur)
            IDLE: begin 
                TIMER_RST <= 1'b1; 
                wait_time <= RAND_VAL; 
                LED_FOUL <= 1'b0; // IDLE�ɖ߂�������FOUL������
            end
            WAIT_STATE: begin
                TIMER_EN <= 1'b1;
                if (STOP_BTN) LED_FOUL <= 1'b1; // �t���C���O���ɓ_��
                if (TIMER_VAL[7:0] >= wait_time) begin
                    TIMER_RST <= 1'b1; // ���蒼�O�Ƀ^�C�}�[��0���Z�b�g
                end
            end
            MEASURE: begin 
                LED_TARGET <= 1'b1; 
                TIMER_EN <= 1'b1; 
            end
            RESULT: begin 
                if (LED_FOUL) LED_FOUL <= 1'b1; // �t���C���O��Ԃ����ʉ�ʂł��ێ�
            end
        endcase
    end
endmodule
