Status: ready-for-agent
Type: AFK
Blocked by: 03

# 04. Multiple-choice and rating questions

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Extend validation and the page to multiple-choice (list of option IDs) and rating (integer within the question's bounds), using the fixed answer shapes from the spec.

## Acceptance criteria

- [ ] Entry-point tests for each type: valid answers store in the fixed shape; unknown options, duplicate options, out-of-range or non-integer ratings are rejected with a reason.
- [ ] The page renders both types and shows a clear message for a missed or invalid answer before submitting.
- [ ] The poll definition checks (slice 07 once merged) and the example poll cover both types.
- [ ] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 4, 5, 11, 26
