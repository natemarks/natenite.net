Status: ready-for-agent
Type: AFK
Blocked by: 03

# 11. Handler event logging, 365-day retention and saved Logs Insights queries

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The function writes one structured JSON log line per request outcome (accepted, rejected with a reason, error) with no email or answer text. Its log group retains entries for 365 days, and the stack defines saved Logs Insights queries for the routine check. No alarms or notifications.

## Acceptance criteria

- [ ] Entry-point tests assert one structured log line per outcome and that no email address or answer text appears in any line.
- [ ] Template assertions: the log group retains 365 days; saved Logs Insights queries exist; no alarm or notification topic exists.
- [ ] The golden file is updated and read.
- [ ] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 52, 53, 54, 55, 56
