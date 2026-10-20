Status: ready-for-human
Type: HITL
Blocked by: 03, 04, 05, 06, 07, 09, 10

# 13. Deploy and verify the simplified stack

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Deploy the simplified stack and verify it. Before deploying: confirm the responses table holds no responses worth keeping (or clear it), because old and new response IDs sort wrongly together; run `make diff-polls` and review it for any replacement of the retained table or bucket, for what the log group rename does on the deployed stack, and for a Site diff limited to expected changes. Then deploy, and verify the respondent-visible behaviour and the new check against production. See the Sequencing constraints in the PRD.

## Acceptance criteria

- [x] The table is confirmed free of responses worth keeping (or cleared) before the deploy. (As of 2026-10-19 the stack is deployed and `describe-table` reports 0 items, but that count refreshes only about every six hours and the logs show 2 accepted submissions on 2026-10-17, so take a real count.) **Done 2026-10-20:** a real scan shows 0 `RESPONSE#` and 0 `EMAIL#` items (0 items scanned in all).
- [x] The diff review shows no replacement of the responses table or the site bucket. The only replacement is the log group (its fixed name forces a new group; the old generated-name group is retained with its earlier lines), and that is recorded. **Done 2026-10-20** (the owner ran `make diff-polls`; see the comment below).
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

## Comments

**2026-10-20, diff review (the owner's `make diff-polls` output, checked by the
agent).** Certificate and Site stacks: no differences. Polls stack, as
expected: the four saved Logs Insights queries destroyed; the log bucket
policy, the log delivery source, destination and delivery, the Glue database
and table, the Athena workgroup and its three named queries destroyed; the
access-log bucket **orphaned** (kept); the log group **replaced** because of
its new fixed name; the submit function updated with the new code and pointed
at the new group. Only IAM change: the two statements on the removed log bucket
policy, both removals. The responses table, the site bucket, the distribution
and the page deployments are not in the diff.

**One thing to expect from the deploy: the Athena workgroup deletion will
probably fail, and that is not fatal.** The old workgroup never set the
recursive-delete option, and it holds 6 query executions (history from the
earlier `make query-logs` runs) besides its 3 named queries; the Athena API
counts executions as contents that block a non-recursive delete. CloudFormation
removes the named queries first. Per the CloudFormation docs, when it cannot
delete a resource that was removed from the template it retries three times,
removes it from the stack anyway and finishes: the stack ends `UPDATE_COMPLETE`
with a `DELETE_FAILED` event and a status reason, and the leftover workgroup
is deleted by hand afterwards:
`aws athena delete-work-group --work-group NateNiteProductionPolls-access-logs --recursive-delete-option`
(the history goes with it; query result files are in the retained log bucket).
I could not confirm the failure in advance, only that it is likely.

**Left behind by design after the deploy, to decide on:**
- The access-log bucket `nateniteproductionpollsst-nateniteproductionpollsa-qenbhgeewyyz`:
  19 objects, about 24 KB, CloudFront logs that include client IP addresses.
- The old log group `NateNiteProductionPollsStack-NateNiteProductionPollsSubmitLogGroup5C4BB9CB-Re8cWuoUj1Kl`:
  365-day retention, about 59 KB, retained when replaced. Nothing else logs
  there once the function points at the new group.
- Not ours to change here: two other log groups (the bucket-deployment and
  auto-delete helper functions) have no retention set.

Still open in this slice: the deploy itself and every check that follows it.
