# CloudGuard AI - Explainable Cloud Threat Response

**Status:** Runnable reference prototype  
**Theme:** Explainability, human oversight, and auditability for high-stakes cloud security

## Source

CloudGuard AI originated in a Responsible AI and Explainability workshop project by Kenneth Amanchukwu, John Nova, and Srinivasa Dinakar. The scenario follows a suspicious account sequence: geographically impossible logins, privilege escalation, unusual storage access, and a high-risk recommendation.

## Research artifacts

- [CloudGuard AI course report - repository edition](../papers/cloudguard-ai-course-report.md)
- [CloudGuard AI research presentation notes](../papers/cloudguard-ai-research-presentation.md)
- [Papers and research-artifact catalog](../papers/README.md)

These artifacts are academic course and presentation materials and are not peer-reviewed publications.

## What the prototype does

- Scores five normalized cloud-risk signals with explicit additive contributions.
- Ranks the factors behind each recommendation.
- Reproduces the workshop's example risk score of 95/100.
- Requires a named human analyst before account disablement can be approved.
- Supports approve, reject, and investigate decisions.
- Records the rationale, timestamp, and a SHA-256 hash of the recommendation.

## Responsible AI controls

| Principle | Prototype control |
| --- | --- |
| Human oversight | Account disablement requires analyst approval. |
| Accountability | Decisions include analyst identity and rationale. |
| Transparency | Contributions are returned for every signal. |
| Auditability | The recommendation is hashed into the audit record. |
| Contestability | Analysts may reject or request investigation. |

## Important limitation

The current engine is a transparent demonstration using synthetic weights, not a validated security model. Feature contribution does not prove correctness or causality, confidence may be overtrusted, and interactions between signals are not modeled.

## Run it

```bash
python -m pip install -e .
assurance-demo cloudguard examples/cloudguard_incident.json
```

The implementation is in [`src/assurance_portfolio/cloudguard.py`](../src/assurance_portfolio/cloudguard.py), with automated tests in [`tests/test_prototypes.py`](../tests/test_prototypes.py).

