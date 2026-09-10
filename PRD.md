# PRD

The product specification lives in **[MASTER-PRD.md](MASTER-PRD.md)** — the single as-built
consolidation (v3.0). Read the relevant section there before designing a feature.

This file previously carried the standalone WhatsApp Channel spec for cycle 2. That cycle is
complete (S1–S11), and the spec has been **incorporated as [§26 WhatsApp Channel (Verify)](MASTER-PRD.md#26-whatsapp)**
with its subsections renumbered 26.1–26.11.

- Deferred work: [MASTER-PRD §G](MASTER-PRD.md#g-known-gaps), mirrored as `TODO(gap):` markers in code.
- Implementation rationale: [docs/decision-log.md](docs/decision-log.md) (D1–D41 cycle 1, D42–D86 the channel).
- What is left before the channel can launch: [docs/whatsapp-launch-runbook.md](docs/whatsapp-launch-runbook.md).

The filename is kept because the `prd-orchestrator` skill declares it as an input: a new cycle
starts by replacing the contents of this file with that cycle's specification.
