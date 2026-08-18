# Verification Benchmark Fixtures

V6 separates three evidence layers so syntax acceptance, synthetic trace results, and RTL behavior are not conflated.

## 1. Seeded trace benchmark

`assurance-demo benchmark` runs deterministic labelled traces for two compact requirement families:

- bounded response: `grant shall assert within 4 cycles after request`
- prohibition: `grant shall never assert while reset`

It reports case accuracy, defect-detection rate, and false positives. These are synthetic traces and are not RTL simulation results.

Implementation: [`verification_benchmark.py`](../src/assurance_portfolio/verification_benchmark.py)

## 2. Standalone assertion tool acceptance

The V5 `VerilatorSVAValidator` builds a standalone probe and asks a concrete Verilator installation to accept the assertion. CI records this as a real external-tool result, but it is still a syntax/tool-support claim rather than proof against a target RTL design.

Implementation: [`sva_validation.py`](../src/assurance_portfolio/sva_validation.py)

## 3. V6 behavioral RTL mutation proof

V6 adds executable SystemVerilog simulation against two labelled RTL implementations:

- [`rtl/handshake_good.sv`](rtl/handshake_good.sv) — intended request/grant implementation; expected to satisfy the four-cycle bound.
- [`rtl/handshake_late_bug.sv`](rtl/handshake_late_bug.sv) — deliberate late-grant mutation; expected to violate the same bound.

Run locally with Icarus Verilog installed:

```bash
assurance-demo rtl-benchmark --rtl-root benchmarks/rtl
```

The V6 runner compiles each RTL module with a generated SystemVerilog testbench and temporal monitor. The monitor pulses `request`, observes `grant`, and requires grant within four sampled cycles. The benchmark is successful only if:

1. `handshake_good` passes,
2. `handshake_late_bug` fails for the bounded-response violation,
3. the mutation-detection rate is 1.0, and
4. the false-positive count is 0.

A compile error or unavailable simulator does **not** count as mutation detection. GitHub Actions installs Icarus Verilog and runs this benchmark as a dedicated `rtl-behavioral-proof` job.

Implementation: [`rtl_behavioral.py`](../src/assurance_portfolio/rtl_behavioral.py)

## Current trust boundary

V6 establishes behavioral detection for this small labelled RTL mutation. It does not yet establish that model-generated assertions detect the mutation better than deterministic/reference properties, nor does one seeded defect establish general verification effectiveness.

The next controlled experiment should compare:

1. deterministic grammar/reference-property baseline,
2. single model-generated artifact,
3. model generator + independent reviewer,
4. model generator + independent reviewer + deterministic tool gate.

Metrics should include parse/tool acceptance, behavioral mutation detection, false positives, vacuity where measurable, abstention/escalation rate, latency, token/tool cost, and human review effort.
