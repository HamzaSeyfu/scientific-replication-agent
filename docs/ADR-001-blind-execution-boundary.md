# ADR-001: Separate target-aware orchestration from blind execution

**Status:** accepted for the first vertical slice

## Context

A scientific reproduction agent can accidentally chase the published answer. If the agent knows the target while fixing dependencies, selecting checkpoints, changing seeds, or choosing among ambiguous evaluation paths, a numerically close result is weaker evidence than an independently obtained result.

The public RECLAIM harness intentionally exposes the metric target to the benchmark agent. Our project tests a stricter protocol.

## Decision

We split the system into two trust domains.

### Target-aware orchestration / verification

May access:

- published claim and target;
- sealing secret;
- final evidence bundle;
- auditor rules.

It may **not** make execution-path decisions based on closeness to the target.

### Blind execution worker

May access:

- pinned repository / released artifacts;
- metric name and experimental scope;
- protocol/configuration information required to execute faithfully;
- runtime failures;
- approved documentation supplied through a future redacting evidence broker.

It may **not** access:

- the published target value;
- target-bearing orchestrator state;
- arbitrary host files;
- unrestricted target-bearing web search once the isolation boundary is enforced.

## Consequences

1. The first benchmark manifest stores reference and executor payload separately.
2. A pre-flight leakage gate rejects obvious numeric target leakage.
3. Local unrestricted shell execution is development-only. Untrusted scientific repositories must run inside an external isolation boundary.
4. Network access for the blind executor must eventually be either disabled after deterministic setup or mediated by a broker that records and redacts evidence.
5. The target is unsealed only after the execution evidence has been finalized.

This ADR intentionally does not claim that hiding one JSON field is sufficient isolation. The sandbox/network boundary is part of the product, not an implementation detail.
