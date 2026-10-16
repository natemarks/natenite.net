Status: ready-for-agent
Type: AFK
Blocked by: 03

# 05. Free-text answers with length and body-size limits

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Add free-text questions capped at 500 characters, with a live remaining-characters count, and make the oversize-body rejection give respondents a clear message instead of a generic block.

## Acceptance criteria

- [ ] Entry-point tests: an answer over 500 characters is rejected with a reason; a body over 6 KB is rejected with payload-too-large before the shared ACL's 8 KB limit applies.
- [ ] The page shows a remaining-characters count and a clear message when a limit is hit.
- [ ] Limits come from the shared constants, not duplicated values.
- [ ] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 6, 7, 62, 63
