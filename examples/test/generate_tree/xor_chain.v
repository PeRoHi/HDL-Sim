module xor_chain #(parameter WIDTH=8) (
    input wire [WIDTH-1:0] in,
    output wire out
);
    wire [WIDTH-1:0] chain;
    assign chain[0] = in[0];
    
    genvar i;
    generate
        for (i = 1; i < WIDTH; i = i + 1) begin : gen_xor
            assign chain[i] = chain[i-1] ^ in[i];
        end
    endgenerate
    
    assign out = chain[WIDTH-1];
endmodule
