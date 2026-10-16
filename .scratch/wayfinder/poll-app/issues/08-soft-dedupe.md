Status: ready-for-agent
Type: AFK
Blocked by: 03

# 08. Soft duplicate handling with a browser token

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The page generates a random browser token on first visit, remembers a prior submission and says so, and sends the token. The server stores it hashed on each response and never rejects repeats.

## Acceptance criteria

- [ ] Page tests (or manual check recorded in the PR): after submitting, reopening the poll in the same browser says it was already answered.
- [ ] Entry-point tests: the token is stored hashed (never raw) on the response; two submissions with the same token are both accepted.
- [ ] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 13, 38, 39
