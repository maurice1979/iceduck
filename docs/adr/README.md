# Architecture Decision Records

This folder holds Architecture Decision Records (ADRs) — short, immutable documents that each capture **one** consequential technical decision: the context that forced it, the decision itself, and its consequences (including trade-offs accepted, not just benefits).

## ADR vs. `docs/plans/`

IceDuck has two related but distinct documentation conventions:

- **`docs/adr/`** (this folder) — atomic decisions. One file per decision, in the standard Context/Decision/Consequences format. Answers "what did we decide, and why, specifically?"
- **[`docs/plans/`](../plans/)** — phase/build-order narratives. Each file covers a build phase end-to-end: the decisions made during it (often referencing the relevant ADR), what was built, and the verification results once it ran. Answers "what happened during this phase of the build?"

An ADR can be written before its decision is implemented (`Status: Proposed`) or after (`Status: Accepted`); a `docs/plans/` phase doc is written once real work happens and typically links back to the ADR(s) it acted on.

## Status values

- **Proposed** — decided in principle, not yet implemented/verified.
- **Accepted** — implemented and, where applicable, verified.
- **Superseded by ADR-XXXX** — no longer current; the superseding ADR explains why.

## Adding a new ADR

Copy [`template.md`](template.md), number it sequentially (`000N-short-title.md`), and fill it in. Keep it short — a page is plenty. Don't edit an ADR's Decision/Context after acceptance to reflect a later change of mind; write a new ADR that supersedes it instead, so the history stays honest.
