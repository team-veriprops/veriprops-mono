"""Dev/QA support domain (non-production only).

Restores the deterministic `POST /dev/reset` + `POST /dev/seed` contract (CLAUDE.md automation
determinism) that autonomous QA and the live e2e drive-through rely on. Production-gated twice:
the router is only mounted in non-prod, and every handler calls `_require_non_prod()` (404 in
prod). No entity of its own — it orchestrates the existing domain models/repos.
"""
