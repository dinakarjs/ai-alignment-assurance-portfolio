module prohibition_bug (
  input  logic clk,
  input  logic rst_n,
  input  logic enable,
  output logic grant
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      grant <= 1'b1; // Seeded defect: grant is asserted during reset.
    else
      grant <= enable;
  end
endmodule
