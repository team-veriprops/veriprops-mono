# Veriprops PRD --- SOPs (Customer, Agent, Admin)

## Overview

This document defines the Standard Operating Procedures (SOPs) for
Customers, Agents, and Admins within Veriprops. It incorporates: -
Progressive Validation - Exception Handling - Confidence Scoring -
Auto-Approval with Manual Override

------------------------------------------------------------------------

# 1. CUSTOMER SOP

## 1.1 Create Verification Request

### Required at Intake

-   Property Location (Google Maps)
-   Property Type
-   Description
-   At least 1 document/image

### Additional Fields (Pre-Verification)

-   Estimated Price
-   Plot Size
-   Survey Plan Number (Optional)
-   Beacon Numbers (Optional)

### Property Owner

-   Full Name

### Seller Information

-   Full Name
-   Company (Optional)
-   Email
-   Phone

### Additional Details (Optional)

------------------------------------------------------------------------

## 1.2 Validation Rules

-   Inline warnings during input
-   Hard validation on submission
-   Cannot submit if required fields missing

------------------------------------------------------------------------

## 1.3 Exception Handling

If unavailable: - User selects "Mark as unavailable" - Must provide: -
Reason - Evidence

------------------------------------------------------------------------

## 1.4 Workflow

DRAFT → SUBMITTED → PAYMENT → ASSIGNED

------------------------------------------------------------------------

# 2. AGENT SOP

## 2.1 Assignment

-   Agent receives job based on type:
    -   Field Agent
    -   Surveyor
    -   Registry Agent
    -   Lawyer

------------------------------------------------------------------------

## 2.2 Data Capture

-   Camera-only uploads (images/videos)
-   Required inputs per role
-   Inline validation warnings

------------------------------------------------------------------------

## 2.3 Submission Rules

-   Cannot submit unless:
    -   Required media provided
    -   Required fields completed OR exception submitted

------------------------------------------------------------------------

## 2.4 Exception Handling

-   Must include:
    -   Reason
    -   Evidence
-   Sent for admin approval

------------------------------------------------------------------------

## 2.5 Workflow

ASSIGNED → IN_PROGRESS → REVIEW

------------------------------------------------------------------------

# 3. ADMIN SOP

## 3.1 Review Queue

-   Prioritized by:
    -   Confidence Score
    -   Flags
    -   Risk level

------------------------------------------------------------------------

## 3.2 Auto-Approval System

### Modes

-   Manual
-   Auto
-   Hybrid (default)

### Conditions for Auto Approval

-   Confidence Score ≥ Threshold
-   Flags ≤ Allowed
-   No critical issues

------------------------------------------------------------------------

## 3.3 Manual Review

Admin reviews: - Evidence - Flags - Agent inputs

Actions: - Approve - Reject - Request revision

------------------------------------------------------------------------

## 3.4 Exception Approval

Admin: - Approves or rejects exceptions - Logs decision

------------------------------------------------------------------------

## 3.5 Workflow

REVIEW → AUTO_APPROVED / PENDING_ADMIN → COMPLETED

------------------------------------------------------------------------

# 4. CONFIDENCE SCORE

## Factors

-   Completeness
-   Consistency
-   Evidence Quality
-   Agent Reliability

## Output

-   Score (0--100)
-   Flags
-   Risk level

------------------------------------------------------------------------

# 5. VALIDATION SYSTEM

## Rules

-   Progressive enforcement by stage
-   No submission without required inputs
-   Exceptions allowed with evidence

------------------------------------------------------------------------

# 6. AUDIT & LOGGING

-   All approvals logged
-   Auto vs manual decisions tracked
-   Exception logs maintained

------------------------------------------------------------------------

# 7. SUCCESS METRICS

-   Submission completion rate
-   Auto-approval rate
-   Agent approval rate
-   Revision rate

------------------------------------------------------------------------

# FINAL PRINCIPLE

Capture fast → Validate progressively → Enforce before trust is assigned
