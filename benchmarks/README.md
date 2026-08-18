# Verification Benchmark Fixtures

V5 introduces two deliberately separate benchmark layers.

## 1. Seeded trace benchmark — executable today

`assurance-demo benchmark` runs deterministic labelled traces for two compact requirement families:

- bounded response: `grant shall assert within 4 cycles after request`
- prohibition: `grant shall never assert while reset`

The benchmark reports case accuracy, defect-detection rate, and false positives. These traces are synthetic and are intended as a reproducible baseline for orchestration and regression testing. They are **not** RTL simulation results.

Implementation: [`verification_benchmark.py`](../src/assurance_portfolio/verification_benchmark.py)

## 2. RTL fixtures — seeded targets for the next execution step

[`rtl/handshake_good.sv`](rtl/handshake_good.sv) implements a small request/grant block whose grant occurs within the intended bound.

[`rtl/handshake_late_bug.sv`](rtl/handshake_late_bug.sv) contains a deliberate late-grant defect. The defect is labelled in source so the fixture can support future simulator/formal comparison and mutation-style evaluation.

The repository does **not** currently claim that CI detects the behavioural difference between these two RTL implementations. V5 validates generated assertion syntax/tool acceptance with a Verilator adapter, while behavioural RTL execution remains a subsequent benchmark extension.

## Intended experiment

The planned comparison is:

1. deterministic V4 grammar baseline,
2. single model-generated artifact,
3. model generator + independent model reviewer,
4. model generator + independent reviewer + deterministic verification tool gate.

Metrics should include parse/tool acceptance, semantic correctness against labelled traces or reference properties, seeded-defect detection, false positives, vacuity where measurable, review escalation rate, latency, token/tool cost, and human review effort.
