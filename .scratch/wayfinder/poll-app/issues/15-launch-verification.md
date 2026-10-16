Status: ready-for-human
Type: HITL
Blocked by: 04, 05, 06, 07, 08, 09, 10, 11, 13

# 15. Launch verification: smoke tests, open inferences, privacy wording, real polls

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The final gate before announcing a poll. Run the end-to-end smoke tests from the build plan, answer the open questions from the research, and settle the launch checklist items that were deliberately left out of the architecture.

## Acceptance criteria

- [ ] All smoke tests from the build plan's first-deploy section have a recorded result.
- [ ] These open questions are answered in the spec's further notes: whether managed rules block ordinary free text; whether a throttled request moves the 4xx or throttle metric; whether WAF blocks appear as 403 in CloudFront logs; the status code used for a closed poll.
- [ ] The privacy notice wording is final, and a decision is recorded on whether any privacy regime applies to collecting an email.
- [ ] Real poll questions are in place, and the example poll is either kept or removed on purpose.
- [ ] The main site is confirmed unaffected.

## Blocked by

- Blocked by 04, 05, 06, 07, 08, 09, 10, 11, 13

## User stories addressed

Spec user stories: Verifies the stories above; closes the open inferences
