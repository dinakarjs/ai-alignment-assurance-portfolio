module handshake_late_bug (
  input  logic clk,
  input  logic rst_n,
  input  logic request,
  output logic grant
);
  logic [2:0] delay_count;
  logic pending;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      grant <= 1'b0;
      delay_count <= '0;
      pending <= 1'b0;
    end else begin
      grant <= 1'b0;
      if (request && !pending) begin
        pending <= 1'b1;
        delay_count <= 3'd0;
      end else if (pending) begin
        delay_count <= delay_count + 3'd1;
        // Seeded defect: grant is delayed beyond the intended four-cycle bound.
        if (delay_count == 3'd5) begin
          grant <= 1'b1;
          pending <= 1'b0;
        end
      end
    end
  end
endmodule
