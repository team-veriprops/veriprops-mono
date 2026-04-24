# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Feature: Verification Lifecycle (Deterministic State Machine)

---

# 1. Objective

Define a **strict, deterministic lifecycle** for property verification that:

- Eliminates ambiguity in operations  
- Supports multi-agent workflows  
- Provides clear, trust-building visibility to customers  
- Ensures admin control and legal defensibility  

---

# 2. Core Principles

1. Deterministic State Machine  
   - No undefined transitions  
   - No hidden states  

2. Dual-Layer Model  
   - Verification (global state)  
   - Tasks (per agent role)  

3. Admin-Controlled Quality Gate  
   - No report reaches customer without approval  

4. Customer Abstraction Layer  
   - Customers see a simplified version  

5. Forward-Only Progression  
   - Except controlled revision loops at task level  

---

# 3. Domain Model

## 3.1 Entities

### Verification
- id  
- verification_id (e.g. VP-2026-0001)  
- status (global state)
- tier  
- property_id  
- customer_id  
- created_at  
- updated_at  

---

### Task
- id  
- verification_id  
- role_type:
  - FIELD_AGENT
  - SURVEYOR
  - REGISTRY_AGENT
  - LAWYER
- assigned_agent_id  
- status  
- submitted_at  
- approved_at  

---

### Report
- id  
- verification_id  
- version  
- status (DRAFT / APPROVED)  
- generated_at  

---

# 4. STATE MACHINES

---

# 4.1 Verification State Machine (GLOBAL)

## States

DRAFT  
SUBMITTED  
PAYMENT_PENDING  
PAID  
IN_PROGRESS  
UNDER_REVIEW  
COMPLETED  
CANCELLED  
FAILED  

---

## Transitions

| From | To | Trigger | Actor | Conditions |
|------|----|--------|------|-----------|
| DRAFT | SUBMITTED | Submit form | Customer | Valid input |
| SUBMITTED | PAYMENT_PENDING | Init payment | System | — |
| PAYMENT_PENDING | PAID | Payment success | System | Verified payment |
| PAID | IN_PROGRESS | First task assigned | Admin | ≥1 required task |
| IN_PROGRESS | UNDER_REVIEW | All tasks submitted | System | ALL = SUBMITTED |
| UNDER_REVIEW | COMPLETED | All tasks approved | System | ALL = APPROVED |
| ANY | CANCELLED | Cancel request | Admin | Refund handled |
| IN_PROGRESS | FAILED | Critical failure | Admin/System | Fraud/inaccessible |

---

## Invariants

- Cannot skip states  
- Cannot move backward  
- COMPLETED is terminal  

---

# 4.2 Task State Machine (PER ROLE)

## States

PENDING  
ASSIGNED  
ACCEPTED  
IN_PROGRESS  
SUBMITTED  
REJECTED  
APPROVED  

---

## Transitions

| From | To | Trigger | Actor |
|------|----|--------|------|
| PENDING | ASSIGNED | Assign agent | Admin |
| ASSIGNED | ACCEPTED | Accept job | Agent |
| ASSIGNED | PENDING | Timeout/unassign | System/Admin |
| ACCEPTED | IN_PROGRESS | Start work | Agent |
| IN_PROGRESS | SUBMITTED | Submit findings | Agent |
| SUBMITTED | APPROVED | Approve | Admin |
| SUBMITTED | REJECTED | Request revision | Admin |
| REJECTED | IN_PROGRESS | Rework | Agent |

---

## Invariants

- Only Admin can APPROVE  
- Only Agent can SUBMIT  
- Only REJECTED → IN_PROGRESS is allowed backward  

---

# 5. 🔗 Derived Global State Logic

| Condition | Result |
|----------|--------|
| Payment incomplete | PAYMENT_PENDING |
| ≥1 task started | IN_PROGRESS |
| ALL tasks submitted | UNDER_REVIEW |
| ALL tasks approved | COMPLETED |
| ANY task rejected | IN_PROGRESS |
| Critical failure | FAILED |

---

# 6. CUSTOMER VIEW

## Visible States

1. Submitted  
2. Payment Confirmed  
3. Verification In Progress  
4. Under Review  
5. Completed  

---

## Expanded “Verification In Progress”
### Customer sees:

- Progress %
- Estimated completion time
- Stage breakdown:
Example:
Registry Check        ✅ Completed  
Field Inspection      ⏳ In Progress  
Survey Verification   ⏳ Pending  
Legal Review          ⏳ Pending  

---

## Customer Actions

| State | Actions |
|------|--------|
| DRAFT | Edit / Submit |
| PAYMENT_PENDING | Retry payment |
| IN_PROGRESS | View progress |
| UNDER_REVIEW | View status |
| COMPLETED | View/download report |
| ANY | Request cancellation |

---

## Restrictions

- No direct agent interaction  
- Cannot modify workflow  
- Cannot approve/reject  

---

# 7. AGENT VIEW
## 7.1 Task Dashboard
Agent sees:
- Assigned tasks
- Role-specific UI
- Deadlines

## 7.2 Task States (Agent Perspective)

| State | Meaning |
|------|--------|
| ASSIGNED | Awaiting acceptance |
| ACCEPTED | Reserved |
| IN_PROGRESS | Work ongoing |
| SUBMITTED | Awaiting review |
| REJECTED | Needs correction |
| APPROVED | Completed |

---

## 7.3 Agent Actions

| State | Actions |
|------|--------|
| ASSIGNED | Accept / Decline |
| ACCEPTED | Start work |
| IN_PROGRESS | Upload evidence |
| IN_PROGRESS | Submit findings |
| REJECTED | Edit & resubmit |

---

## 7.4 Restrictions
- Cannot approve  
- Cannot affect other agents  
- Cannot change verification state  

---

# 8. ADMIN VIEW
## 8.1 Verification Control Panel
### Admin sees:
- Full verification breakdown
- All tasks + statuses
- Customer + property data

## 8.2 Admin Actions

### Verification Level
- Assign / reassign agents  
- Cancel verification  
- Mark failure  
- Approve final report  

---

### Task Level
- Assign agent  
- Reassign  
- Approve submission  
- Reject submission  

---

## 8.3 Multi-Agent View
### Example:
Field Inspection      ✅ Submitted  
Survey               ⏳ In Progress  
Registry             ✅ Approved  
Legal                ⏳ Pending  

---

## 8.4 Admin Authority Rules
- Admin is final authority
- All approvals must pass admin
- System auto-transitions AFTER admin actions

---

# 9. Progress & SLA

## Progress Formula

Progress = Approved Tasks / Total Tasks  

---

## SLA

Each task has:
- expected_duration  
- deadline  

System flags:
- Overdue tasks  
- Delays  

---

# 10. Edge Cases

### 10.1 Partial Completion
Some tasks complete, others pending:
→ Verification remains IN_PROGRESS  

---

### 10.2 Rejection Loop
Task rejected:
→ Back to IN_PROGRESS
→ Does NOT affect other tasks

---

### 10.3 Agent No-Show
- Timeout → Reassign
- Task returns to PENDING  

---

### 10.4 Conflicting Reports
- Flag raised
- Admin review required
- Verification paused if needed

---

### 10.5 Tier Upgrade
- New tasks created
- Lifecycle continues in IN_PROGRESS 

---

# 11. Audit & Compliance

- All transitions logged:
  - actor  
  - timestamp  
  - from state  
  - to state  
- Required for:
  - Legal defensibility
  - Dispute resolution

---

# 12. API (High Level)

## Verification
- POST /verifications  
- GET /verifications/:id  
- POST /verifications/:id/cancel  

---

## Tasks
- POST /tasks/:id/assign  
- POST /tasks/:id/accept  
- POST /tasks/:id/start  
- POST /tasks/:id/submit  
- POST /tasks/:id/approve  
- POST /tasks/:id/reject  

---

# 13. Success Metrics

- Avg completion time  
- % without revision  
- Task acceptance time  
- Customer and Admin trust (rating)  

---

# 14. Future Extensions

- Auto agent assignment (Availability, Location, Agent type, Rating - based on property Estimated cost)
- AI risk scoring  
- Real-time collaboration  
- Escrow integration  

---

# Summary

This lifecycle ensures:

- No ambiguity → deterministic transitions
- No chaos → strict role control
- High trust → transparent progress
- Scalability → multi-agent orchestration 
