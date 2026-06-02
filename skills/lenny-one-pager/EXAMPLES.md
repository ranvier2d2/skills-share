# Lenny One-Pager Examples

## Reusable Skeleton

```markdown
# [Product / Project Name]

## 1. Description

[2-3 sentences: what it does, who it is for.]

## 2. Problem

[One testable hypothesis: what is going wrong and why it matters.]

## 3. Why

- [Evidence point 1]
- [Evidence point 2]
- [Evidence point 3]
- [Optional evidence point 4]
- [Optional evidence point 5]

Devil's advocate: [Best reason this may not be real, urgent, or causal.]

## 4. Success

Primary metric: [metric] moves from [baseline] to [target] by [date/window].

## 5. Audience

[Specific segment, platform, geography, and why this segment first.]

## 6. What

1. User starts at [context].
2. They see/do [key interaction].
3. The result is [outcome].

## 7. How

Approach: [build / experiment / prototype / manual-first].

Key risks or dependencies:
- [Risk/dependency 1]
- [Risk/dependency 2]

## 8. When

| Milestone | Target Date | Owner |
|-----------|-------------|-------|
| Design complete | [Date] | [Name] |
| Build complete | [Date] | [Name] |
| Internal testing | [Date] | [Name] |
| Ship / experiment start | [Date] | [Name] |
| Results review | [Date] | [Name] |

Confidence: [High/Medium/Low]. [What could slip and why.]
```

## Mini-Example

```markdown
# Appointment Recovery for KineRod

## 1. Description

Appointment Recovery helps medical centers recover appointment capacity when patients cannot attend. Patients can confirm, reschedule, or release an appointment through WhatsApp, while the center gets auditable operational state.

## 2. Problem

Patients who cannot attend often fail to cancel early enough because the current workflow is high-friction, causing recoverable appointment slots to become lost capacity.

## 3. Why

- WhatsApp is already used by patients, but many conversations are not operationally actionable.
- No-show and late cancellation directly reduce effective agenda capacity.
- Staff-dependent follow-up makes outcomes inconsistent across branches and shifts.

Devil's advocate: We still need KineRod baseline data to prove the largest capacity leak is cancellation recovery rather than acquisition, scheduling, or provider availability.

## 4. Success

Primary metric: increase recovered released slots by 10-15% during the pilot window without increasing human follow-up load.

## 5. Audience

Start with patients who already have an appointment at KineRod and are contacted by WhatsApp within the reminder window. This segment has the clearest operational intent and the lowest adoption friction.

## 6. What

1. Patient receives a polite appointment reminder.
2. They confirm, reschedule, or release the appointment in natural language or through quick replies.
3. KineRod gets updated appointment state and a recoverable slot when the patient cannot attend.

## 7. How

Approach: manual-supported pilot with automated WhatsApp workflow and operational audit.

Key risks or dependencies:
- Real Kopland availability and state reconciliation.
- Human escalation process for ambiguous or out-of-domain cases.

## 8. When

| Milestone | Target Date | Owner |
|-----------|-------------|-------|
| Demo workflow ready | 2026-05-26 | Ranvier |
| Pilot metrics defined | TBD | KineRod + Ranvier |
| Pilot start | TBD | KineRod |
| Results review | TBD | KineRod + Ranvier |

Confidence: Medium. Timeline depends on production WhatsApp sender approval and access to baseline operational data.
```
