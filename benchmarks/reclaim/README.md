# RECLAIM benchmark integration

This directory contains small, explicit case manifests used to measure the project against the public RECLAIM benchmark.

## Why the manifest has two sections

RECLAIM's released rows expose the target value to the reproduction agent. Our experimental hypothesis is stricter: the execution agent should know **what** to measure and **how** to run the intended protocol, but should not know the published numeric answer while it is making recovery decisions.

Each case therefore contains:

- `reference`: orchestration/verifier-only target metadata;
- `blind_executor`: the payload allowed into the execution workspace.

`replicator.benchmarks.reclaim` rejects a blind payload if the target's common textual forms appear in it. This is only a pre-flight guardrail. The real isolation boundary must also prevent the blind worker from reading target-bearing host files or freely retrieving the paper/result through the network.

## First case: AirRep (2505.18513)

We start with the RECLAIM development case for AirRep because its released code, public evaluation dataset, and pretrained model make it a cheap Run-tier-style vertical slice. The goal is not to tune toward the published number. The goal is to run the official evaluation faithfully, capture a real LDS metric, and only then let the verifier unseal the reference value.
