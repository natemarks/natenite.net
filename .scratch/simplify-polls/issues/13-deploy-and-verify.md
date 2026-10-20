Status: ready-for-human
Type: HITL
Blocked by: 03, 04, 05, 06, 07, 09, 10

# 13. Deploy and verify the simplified stack

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Deploy the simplified stack and verify it. Before deploying: confirm the responses table holds no responses worth keeping (or clear it), because old and new response IDs sort wrongly together; run `make diff-polls` and review it for any replacement of the retained table or bucket, for what the log group rename does on the deployed stack, and for a Site diff limited to expected changes. Then deploy, and verify the respondent-visible behaviour and the new check against production. See the Sequencing constraints in the PRD.

## Acceptance criteria

- [ ] The table is confirmed free of responses worth keeping (or cleared) before the deploy. (As of 2026-10-19 the stack is deployed and `describe-table` reports 0 items, but that count refreshes only about every six hours and the logs show 2 accepted submissions on 2026-10-17, so take a real count.)
- [ ] The diff review shows no replacement of the responses table or the site bucket. The only replacement is the log group (its fixed name forces a new group; the old generated-name group is retained with its earlier lines), and that is recorded.
- [ ] After deploy the poll page loads, a test submission is accepted (single choice and at least one other question type), the response ID has the new shape, and the log line has exactly the trimmed fields.
- [ ] Closed-poll, retry-and-busy and already-answered behaviour are unchanged for a respondent.
- [ ] `make check-polls` against production returns a summary that includes the test submission and daily metrics.
- [ ] The log fetch is checked against the real log group: the real `aws logs filter-log-events` output has the shape the jq program expects (`events[].timestamp` and `events[].message`, pages merged), and the test submission's line appears in `.polls-check/handler.jsonl` with its timestamp.
- [ ] `make dump-poll` and the email commands (dry-run) still work.
- [ ] The access-log bucket the removal leaves behind is dealt with (the stack was deployed on 2026-10-16 and has it: logical ID `NateNiteProductionPollsAccessLogBucket9851091C`, bucket `nateniteproductionpollsst-nateniteproductionpollsa-qenbhgeewyyz`, retained on delete): if it holds log files with client IP addresses you do not want, empty and delete it, otherwise record that it was kept on purpose.
- [ ] The main site (apex and www) is unaffected.

## Blocked by

- Blocked by [One definition of the polls hostname](03-one-polls-hostname.md)
- Blocked by [Trim the function's log line and consolidate its logging tests](04-trim-the-log-line.md)
- Blocked by [Timestamp-plus-random response IDs](05-timestamp-response-ids.md)
- Blocked by [Remove the access-log layer](06-remove-the-access-log-layer.md)
- Blocked by [Pin the log group name and drop the saved queries](07-pin-log-group-and-drop-saved-queries.md)
- Blocked by [Log check part 1: errors and rejections from the function's log](09-log-check-errors-and-rejections.md)
- Blocked by [Log check part 2: daily metrics](10-log-check-daily-metrics.md)

## User stories addressed

Spec user stories: 24, 25, 26, 42
