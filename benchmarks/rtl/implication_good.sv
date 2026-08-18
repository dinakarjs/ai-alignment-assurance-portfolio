module implication_good (
  input  logic request,
  output logic busy
);
  assign busy = request;
endmodule
