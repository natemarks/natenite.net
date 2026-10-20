Status: ready-for-agent
Type: AFK
Blocked by: 06

# 07. Pin the log group name and drop the saved queries

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Give the function's log group a fixed name derived from the stack prefix so tooling can find it, keeping 365-day retention and retention on stack deletion, and remove the saved Logs Insights queries (their definitions and the resources). Update the log group test, remove the saved-queries test and regenerate the Polls golden file. See [Grill: owner scripts and docs](../tickets/06-grill-owner-scripts-and-docs.md), decisions 2 and 3.

## Acceptance criteria

- [x] The log group has a fixed, documented name, 365-day retention and a retain-on-delete policy.
- [x] No saved query resources remain, and the saved-queries test is removed.
- [x] The golden diff shows only the log group name and the removed queries.
- [x] The PR states that on an already-deployed stack the rename creates a new group while the retained old group keeps earlier lines; the diff review is part of the deploy slice.
- [x] `make static` passes.

## Blocked by

- Blocked by [Remove the access-log layer](06-remove-the-access-log-layer.md)

## User stories addressed

Spec user stories: 10, 23

## Comments

Done (uncommitted) in `stack/polls.py`, `tests/unit/stack/test_polls.py` and
the Polls golden file.

- **Name:** the log group is `/natenite/production/polls/submit`, built by a new
  `PollsInput.log_group_name()` next to `table_name()` (`/<app name
  lowercase>/<app env>/polls/submit`). That method is the single source for the
  name; the log-check slices should use it rather than repeat the formula. The
  group keeps 365-day retention and the retain-on-delete and
  retain-on-replacement policies.
- **Queries:** removed the `SAVED_QUERIES` constant, the loop that created the
  four query definitions (the plan said two; the stack still had all four) and
  the saved-queries test. The log group test now pins the exact name and the
  365 days.
- **Golden diff:** the four `AWS::Logs::QueryDefinition` resources removed, the
  log group gains `LogGroupName`, nothing else changed (no resources added, the
  log group's logical ID is unchanged, other sections equal).
- **Verified against the CloudFormation reference** (`AWS::Logs::LogGroup`):
  `LogGroupName` is "Update requires: Replacement"
  (https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-logs-loggroup.html).
  So on an already-deployed stack the deploy creates a new group with the fixed
  name and, because of the retain-on-replacement policy, leaves the old
  generated-name group (and its earlier lines) in the account. The function's
  logging configuration then points at the new group. The deploy slice's diff
  review covers this.
- `make static` and `make static-check` exit 0: pylint 10.00/10, 260 Python
  tests (261 before, minus the saved-queries test) and 41 Node tests.
- Not touched: the owner guide still describes saved queries.
