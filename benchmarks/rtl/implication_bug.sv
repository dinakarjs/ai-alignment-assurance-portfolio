module implication_bug (
  input  logic request,
  output logic busy
);
  assign busy = 1'b0; // Seeded defect: request no longer implies busy.
endmodule
