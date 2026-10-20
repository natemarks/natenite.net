Status: ready-for-agent
Type: AFK
Blocked by: 06, 09

# 12. Update the launch-verification issue and build plan

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Before launch verification runs, update the earlier effort's launch-verification issue and build plan to the simplified design: remove the access-log checks (the open question about whether firewall blocks appear as 403s in the CloudFront logs, and the log-delivery and Athena smoke tests), mark the earlier log-delivery and Athena issues as superseded, and add a smoke test that `make check-polls` runs against production and returns a summary. See [Grill: planning docs after the build](../tickets/07-grill-planning-docs-after-build.md), decision 3.

## Acceptance criteria

- [ ] The launch-verification issue and build plan contain no check for a component that no longer exists.
- [ ] The earlier log-delivery and Athena issues carry a superseded note.
- [ ] A smoke test for `make check-polls` is added to the launch checklist.
- [ ] No other launch criteria are changed.

## Blocked by

- Blocked by [Remove the access-log layer](06-remove-the-access-log-layer.md)
- Blocked by [Log check part 1: errors and rejections from the function's log](09-log-check-errors-and-rejections.md)

## User stories addressed

Spec user stories: 38
