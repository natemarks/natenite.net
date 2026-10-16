Status: ready-for-human
Type: HITL
Blocked by: 03

# 10. Rate rule on the shared ACL and Lambda concurrency cap of 2

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Add the per-IP rate-based rule to the existing shared web ACL (counts only POST to the submit path on the polls hostname, 20 per 5 minutes, action block) and set the function's reserved concurrency from settings. This edits the live main-site ACL.

Human gate: review the Site diff in isolation, deploy, and run the throttling checks.

## Acceptance criteria

- [ ] The Site golden file changes only by the new rate rule, and template assertions confirm its scope (host, path, method), limit, window and action.
- [ ] The function's reserved concurrency is read from the polls settings and asserted in the template.
- [ ] After deploy: more than 20 submit POSTs from one IP in 5 minutes are blocked; page views are not counted; driving concurrency above the cap returns HTTP 429.
- [ ] While testing, record which of Url4xxCount, Throttles and ConcurrentExecutions moved for a throttled request, and add the answer to the spec's further notes.
- [ ] The main site (apex and www) is unaffected.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 58, 59, 60, 61, 65
