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
- [x] `make check-polls` against production returns a summary that includes the test submission and daily metrics. **Done 2026-10-20:** `make -s check-polls` exits 0 with `logs` (1 request, accepted, 0 errors), 11 metric series and `incomplete_metrics` empty.
- [x] The log fetch is checked against the real log group: the real `aws logs filter-log-events` output has the shape the jq program expects (`events[].timestamp` and `events[].message`, pages merged), and the test submission's line appears in `.polls-check/handler.jsonl` with its timestamp. **Done 2026-10-20:** the new log group holds five real events for the test submission (`INIT_START`, `START`, one JSON line, `END`, `REPORT`); events have `timestamp` and `message` as the program expects; the fetch kept only the JSON line, with its timestamp.
- [x] `make dump-poll` and the email commands (dry-run) still work. **Done 2026-10-20:** `dump-poll` returns `[]` (the table is empty); `purge-emails` and `delete-email` dry runs report 0 records.
- [x] The access-log bucket the removal leaves behind is dealt with (the stack was deployed on 2026-10-16 and has it: logical ID `NateNiteProductionPollsAccessLogBucket9851091C`, bucket `nateniteproductionpollsst-nateniteproductionpollsa-qenbhgeewyyz`, retained on delete): if it holds log files with client IP addresses you do not want, empty and delete it, otherwise record that it was kept on purpose. **Done 2026-10-20:** the owner emptied and deleted it (a `head-bucket` now returns 404).
- [x] The main site (apex and www) is unaffected. **Done 2026-10-20:** `https://natenite.net/` and `https://www.natenite.net/` both return 200 with the same 7,392-byte page.

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

**2026-10-20, after the owner's deploy (output pasted by the owner; the agent
then checked the state read-only).**

- **Result:** `UPDATE_COMPLETE`, "Update successful. One or more resources could
  not be deleted." Deployment took 405 s. Certificate and Site stacks: no
  changes. CDK printed "Some resources failed to delete but were skipped".
- **The one failure:** `NateNiteProductionPollsAccessLogQueriesWorkGroup8934E74A`
  (`AWS::Athena::WorkGroup`, `NateNiteProductionPolls-access-logs`),
  `DELETE_FAILED` three times with "WorkGroup ... is not empty" (HTTP 400). As
  predicted in the diff review: the workgroup holds 6 query executions and the
  old definition never set the recursive-delete option. CloudFormation did
  delete its 3 named queries first (0 remain). Per the CloudFormation docs the
  resource was then dropped from the stack, so the stack itself is healthy and
  needs no further action.
- **Everything else in the removal went through:** the Glue database and table
  (`EntityNotFoundException`), the log delivery source, destination and delivery
  (none left), the saved Logs Insights queries (none left). The function now
  logs to `/natenite/production/polls/submit` and has the new code.
- **The agent tried to delete the leftover workgroup** with
  `aws athena delete-work-group --recursive-delete-option`; the permission
  classifier denied the command and it was not retried or worked around. It is
  left for the owner (command in the cleanup list below).
- **Verified read-only after the deploy:** a full `make -s check-polls` against
  production exits 0 and prints one document with `logs`, `metrics` and
  `incomplete_metrics`; 11 metric series, none incomplete; the log half reports
  0 requests because the new log group is empty (0 bytes) until the function is
  next invoked.

**Cleanup list (what is left in the account):**
1. Athena workgroup `NateNiteProductionPolls-access-logs` (the failure): delete
   with `aws athena delete-work-group --region us-east-1 --work-group NateNiteProductionPolls-access-logs --recursive-delete-option`.
   Removes only its query history; result files are in the retained bucket.
2. Access-log bucket `nateniteproductionpollsst-nateniteproductionpollsa-qenbhgeewyyz`
   (retained by design): 19 objects, about 24 KB, CloudFront logs with client
   IP addresses. It no longer belongs to any stack. Delete it or keep it on
   purpose; its own 365-day expiry rule still applies to the objects.
3. Old log group `NateNiteProductionPollsStack-NateNiteProductionPollsSubmitLogGroup5C4BB9CB-Re8cWuoUj1Kl`
   (retained by design): about 59 KB of earlier function log lines, 365-day
   retention, no longer written to. It expires on its own; delete only for
   tidiness.

Still open: the checks that need a real submission (the new response ID shape,
the trimmed log fields, the test submission appearing in `check-polls`), the
live-log-shape check against the new group, the main site check, and the three
cleanup decisions above.

**2026-10-20, a one-off target for cleanup item 2 (uncommitted, in the
`Makefile`):** `make delete-orphaned-bucket bucket=<name> [yes=1]`. Dry run by
default. It refuses unless the name matches the pattern CloudFormation
generated for this bucket (derived from the stack's own name and the log
bucket's logical ID, not typed in), no stack owns the bucket (a lookup by
physical ID must fail), and the bucket was never versioned; then it empties and
deletes it. Tested without `yes=1`: no argument, an unrelated name and the live
site bucket are refused; a right-pattern name that does not exist fails
cleanly; the real bucket's dry run lists 19 objects and 24,102 bytes and leaves
it untouched. The delete path itself has not been run. **Remove the target
after use** (its help text says so). A tag check was planned and dropped: the
bucket carries only the project's shared tags, which prove nothing.

**2026-10-20, cleanup done.** The owner deleted the leftover Athena workgroup
(`list-work-groups` now shows only `primary`) and, with the one-off Make target,
emptied and deleted the orphaned access-log bucket (404 on `head-bucket`). The
stack is `UPDATE_COMPLETE`. The one-off target has been removed from the
`Makefile`, which is identical to the last commit again; it was an inline
recipe, so there was no module to remove. The old log group is kept on purpose
(about 59 KB, expires on its own after 365 days); the target was never meant
for it.

**2026-10-20, more read-only checks.** The polls page `/nov20267s-in-603` and
its definition file `/definitions/nov20267s-in-603.json` return 200. An unknown
address such as `/nope` also returns 200 with the same shared page (1,635
bytes), by design: the rewrite function serves the page for any address without
a file extension, and the page itself shows "poll not found" after it fails to
load a definition. So a 200 does not mean the poll exists; only a browser (or
fetching `/definitions/<id>.json`) tells you that.

**Left in slice 13, all needing a real submission:** the page accepting a test
answer, the new response ID shape and trimmed log fields on a real line, the
test submission appearing in `make -s check-polls`, the live log-line shape
against the new (still empty) log group, and the closed-poll, retry-and-busy
and already-answered browser behaviour.

**2026-10-20, the owner's test submission (checked read-only).**
- Page and submit: accepted, HTTP 201 in the log, for the live poll
  `nov20267s-in-603` (answers `sat-nov-7` and `sun-nov-15`), with an email
  address given.
- Stored: `RESPONSE#20261020T103723107676Z-f8faa28a1d4177e6` (the new ID shape:
  UTC time to the microsecond, `Z-`, 16 hex digits), `pollVersion` 1, a browser
  token hash present, and one linked `EMAIL#20261020T103723107676Z-f8faa28a1d4177e6`
  record with the same suffix. The log line's `responseId` is the same ID.
- Log line, exactly: `level`, `outcome`, `status`, `pollId`, `responseId`,
  `bodyBytes` (155), `requestId`, plus `timestamp` added by the fetch. No
  email, answer text, token or CloudFront request ID.
- Metrics: the function's invocation for that UTC day showed in CloudWatch a
  couple of minutes after the submission (the first `check-polls` run was just
  too early, so reporting lag, not a fault).
- **The first criterion stays open on purpose:** it asks for a test submission
  to a single-choice question and at least one other type, but the only live
  poll has one multi-choice question. The page, the new ID and the log fields
  are confirmed; single-choice storage is covered by the unit tests and not
  exercised live. Say if that is enough to tick it, or publish a poll with a
  single-choice question to test it.
- **Test data to remove** (the owner's call; it is the only data in the table):
  the response, with
  `aws dynamodb delete-item --region us-east-1 --table-name natenite-production-polls-responses --key '{"pk":{"S":"POLL#nov20267s-in-603"},"sk":{"S":"RESPONSE#20261020T103723107676Z-f8faa28a1d4177e6"}}'`,
  and the email record with `make purge-emails days=0 yes=1` (deletes every
  email record; there is exactly one) or `make delete-email email=<address> yes=1`.

**Left in slice 13:** the first criterion above, and the closed-poll,
retry-and-busy and already-answered behaviour in a browser.

