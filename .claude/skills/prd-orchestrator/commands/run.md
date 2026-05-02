# Run Command

## Step 1: Load state
Read:
- PRD analysis
- architecture spec
- execution plan
- decision log
- progress
- git diff/status

---

## Step 2: Select execution batch

Dynamically choose:
- 1 large slice OR
- 2–5 small slices

based on:
- dependency readiness
- risk level
- schema/auth impact
- integration complexity

---

## Step 3: Implement slices

For each slice:
- implement code
- update DB/schema if needed
- add tests
- validate behavior

---

## Step 4: Self-audit (MANDATORY)

Check:
- PRD compliance
- architecture compliance
- security correctness
- missing tests
- race conditions
- API consistency
- migration safety

Fix issues before stopping.

---

## Step 5: Update state

Update:
- docs/progress.md
- docs/requirements-matrix.md
- docs/decision-log.md (if needed)

---

## Step 6: Clarification check

If new ambiguity discovered:
STOP and ask user:

CLARIFICATION REQUIRED DURING EXECUTION

---

STOP after safe checkpoint.