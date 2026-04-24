# Veriprops PRD --- Report Versioning & Change Tracking System

## Overview

This document defines the Versioning System for Veriprops reports,
ensuring that every verification result is immutable, traceable, and
auditable over time.

Core principles: - Reports are immutable snapshots - Updates create new
versions (never overwrite) - Full change tracking between versions -
Confidence evolution over time - Auto-approval works per version

------------------------------------------------------------------------

# 1. CORE PRINCIPLE

Every report is a snapshot in time.

-   No updates to existing reports
-   Every change creates a new version
-   Full audit trail must be preserved

------------------------------------------------------------------------

# 2. DATA MODEL

## 2.1 PropertyReport

-   id
-   property_id
-   version (v1, v2, v3...)
-   previous_version_id
-   status (draft, final)
-   confidence_score
-   flags
-   data_snapshot (JSON)
-   generated_summary
-   change_summary
-   created_at
-   created_by (system \| admin \| recheck)

------------------------------------------------------------------------

## 2.2 ReportChange (Diff Tracking)

-   report_id
-   field
-   old_value
-   new_value
-   change_type (added, updated, removed)

------------------------------------------------------------------------

## 2.3 ConfidenceHistory

-   property_id
-   version
-   score
-   timestamp

------------------------------------------------------------------------

# 3. VERSION CREATION

## 3.1 Triggers

### Automatic

-   Re-verification request
-   New agent submission after completion
-   System-triggered re-evaluation

### Manual

-   Admin triggers recheck
-   Dispute resolution

------------------------------------------------------------------------

## 3.2 Workflow

v1 → Completed\
→ Recheck triggered\
→ v2 created\
→ Goes through full workflow\
→ Becomes latest version

------------------------------------------------------------------------

# 4. CHANGE TRACKING

## 4.1 Diff Generation

System compares: - Previous version snapshot - New version snapshot

Outputs: - Field-level differences - Change type classification

------------------------------------------------------------------------

## 4.2 Change Summary

Auto-generated human-readable summary:

Example: "Ownership updated. Registry data changed. Confidence score
increased from 72 to 88."

------------------------------------------------------------------------

# 5. VERSION HISTORY UI

## 5.1 Customer View

Display: - Version number - Confidence level - Date

Example:

v2 (Latest) --- High Confidence\
v1 --- Moderate Confidence

------------------------------------------------------------------------

## 5.2 Version Details

Each version shows: - Full report - Evidence - Flags - Confidence score

------------------------------------------------------------------------

## 5.3 Change Highlighting

-   Improvements (green)
-   Risks (red)
-   Minor changes (yellow)

------------------------------------------------------------------------

# 6. ADMIN CONTROLS

Admins can: - View all versions - Compare versions side-by-side -
Trigger re-verification - Review change history

------------------------------------------------------------------------

# 7. AUTO-APPROVAL INTEGRATION

Each version independently: - Runs validation - Gets confidence score -
Goes through auto-approval logic

Different versions may have different approval paths.

------------------------------------------------------------------------

# 8. CONFIDENCE EVOLUTION

Track score changes across versions.

Example:

v1 → 72\
v2 → 88\
v3 → 65

Used for: - Risk detection - User transparency - Analytics

------------------------------------------------------------------------

# 9. AUDIT & COMPLIANCE

Each version must store: - Timestamp - Agent IDs involved - Data
sources - Evidence references

Purpose: - Legal protection - Transparency - Dispute resolution

------------------------------------------------------------------------

# 10. VALIDATION RULES

-   Version cannot be created without valid submission
-   All validation engines apply per version
-   Exceptions must be resolved or approved

------------------------------------------------------------------------

# 11. RISKS & MITIGATION

## Too many versions

-   Restrict rechecks to paid or admin-triggered

## User confusion

-   Highlight latest version clearly
-   Collapse older versions

## Data inconsistency

-   Store full snapshot per version
-   Avoid live dependency

------------------------------------------------------------------------

# 12. IMPLEMENTATION PHASES

## Phase 1

-   Version table
-   Snapshot storage
-   Version increment logic

## Phase 2

-   Diff engine
-   Change summary generator
-   Version history UI

## Phase 3

-   Confidence trend visualization
-   Risk insights

------------------------------------------------------------------------

# FINAL PRINCIPLE

Every report is a snapshot. Trust is built over time, not in a single
verification.
