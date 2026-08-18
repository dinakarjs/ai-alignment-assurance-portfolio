module prohibition_good (
  input  logic clk,
  input  logic rst_n,
  input  logic enable,
  output logic grant
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      grant <= 1'b0;
    else
      grant <= enable;
  end
endmodule
