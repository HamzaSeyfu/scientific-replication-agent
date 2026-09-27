# Scientific Replication Agent (working title)

Prototype for the Nebius × NVIDIA Global AI Hackathon.

## Goal

Build an **adversarial, evidence-first autonomous scientific replication system**. The executor should reproduce a paper's experimental protocol without seeing the published target value. A separate verifier unseals the target only after execution and issues a deterministic, auditable verdict from real artifacts.

## First vertical slice

1. Parse one real paper and isolate one scalar claim.
2. Seal the published target away from the executor.
3. Use Nemotron through Nebius Token Factory for planning / recovery.
4. Run the actual repository in an isolated environment.
5. Record every intervention and source.
6. Unseal only after execution.
7. Emit `evidence.json` with the observed value, provenance and verdict.

## What exists now

- sealed-target trust boundary;
- deterministic scalar verifier;
- evidence/provenance data model;
- Nebius/Nemotron OpenAI-compatible client;
- explicit Veritas integration boundary;
- offline smoke test and unit tests.

This repository intentionally does **not** claim a successful scientific reproduction yet. The offline demo tests the trust boundary only.

## Run the smoke test

```bash
python -m replicator.cli --demo --output evidence.json
```

## Test

```bash
pytest -q
```

## Upstream plan

We intend to integrate with ChicagoHAI/Veritas through its backend abstraction rather than reimplementing its replication pipeline. Veritas is Apache-2.0 licensed; any reused upstream code or bundled assets must retain the required attribution/NOTICE information.
