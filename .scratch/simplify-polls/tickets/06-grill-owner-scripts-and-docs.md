---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: owner scripts and docs

## Question

The owner reads results through three scripts (`dump_poll.py`,
`manage_emails.py`, `query_logs.py`), each with tests and a Makefile target,
and the how-to lives in `POLLS.md` (309 lines) beside the effort files under
`.scratch/wayfinder/poll-app/`. Which scripts stay as separate tools, which
merge into one CLI or disappear, and what is the minimum documentation that
keeps the app operable? Blocked by the observability decision because
`query_logs.py` may go.

## Resolution

Decided with the human, one branch at a time. The grilling changed the shape
of the question: the human still needs to read the handler log to identify and
troubleshoot problems, and wants one way to surface problems across every
source "regardless of location", with a 90-day lookback. Facts: after
[Grill: observability layers](01-grill-observability-layers.md) there is one
log source (the handler log group, kept 365 days) plus CloudWatch metrics that
cover the dropped access logs (WAF `BlockedRequests` per rule, Lambda `Errors`
and `Throttles`, the distribution's error rate). `query_logs.py` only ever read
the Athena access logs, never the handler log, so the handler log had no
terminal path at all, only the console. The AWS docs confirm `FilterLogEvents`
lists a log group's events for a time range and filter pattern, paged
(https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_FilterLogEvents.html),
and that hourly metric data is kept 455 days
(https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_concepts.html);
only the 455-day figure was confirmed, so one-minute data's 15 days and the
other tiers are unverified here.

1. **Check the logs by downloading them and searching locally, with no
   Python.** Three Make targets, each defaulting to `days=90`:
   - `make fetch-logs` runs `aws logs filter-log-events` over the handler log
     group and writes `.polls-check/handler.jsonl` (gitignored).
   - `make fetch-metrics` runs `aws cloudwatch get-metric-data` from a stored
     query file (for example `scripts/polls_metrics.json`) and writes
     `.polls-check/metrics.json`: WAF blocked requests by rule, Lambda errors
     and throttles, the distribution's 5xx rate, all with **daily periods**
     (one-minute data is only kept 15 days). Exact metric names and dimensions,
     notably for CloudFront-scope WAF metrics, are **unverified** and get
     confirmed when building.
   - `make check-polls` runs both fetches, then prints one JSON summary with
     stored jq files (for example under `scripts/jq/`): `ERROR` lines,
     rejections counted by reason, metric totals per day.
   The log lines hold no email or answer text by design, so a local copy is
   safe. Rejected: saved Logs Insights queries only (asynchronous
   start/poll/fetch from a terminal is why `query_logs.py` was 154 lines with
   161 lines of tests; the console path gives an agent session nothing to
   run; it cannot cover metrics); a `query_logs.py` rewrite for Logs Insights
   (about the old script's size plus tests); `aws logs tail` alone (raw lines,
   no summary, no metrics).
   Costs accepted: the shell and jq are not covered by `make static`, so a
   typo surfaces on first run (a small fixture test for the jq files could
   close that, optional); `jq` must be installed (`POLLS.md` already uses it).
2. **The stack pins the log group name** so the commands can find it (today
   it is generated and not output). If the stack is already deployed, renaming
   the group creates a new one and the retained old group keeps earlier lines;
   confirm before deploying, as for the response-ID change in
   [Grill: submit handler structure](03-grill-handler-structure.md).
3. **Drop the two saved Logs Insights queries** (`polls/errors`,
   `polls/rejections-by-reason`), so each question is defined once, in jq.
   This amends decision 4 of ticket 01 and makes the inlining in decision 3 of
   [Grill: stack layout and WAF rule ownership](04-grill-stack-layout.md)
   moot. Two `CfnQueryDefinition` resources, the query strings and their test
   leave the stack. The log group stays. `POLLS.md` lists the log fields so an
   ad hoc Logs Insights query can still be written in the console.
   Rejected: keeping them for console convenience (the same questions would be
   defined twice and drift when log fields change).
4. **Keep the two owner scripts and their three Make targets.**
   `dump_poll.py` (read-only) and `manage_emails.py` (destructive, dry-run by
   default) stay separate, with `dump-poll`, `purge-emails` and `delete-email`.
   `query-logs` is removed; `fetch-logs`, `fetch-metrics` and `check-polls`
   are added; `diff-polls` and `deploy-polls` stay. The Make targets hide the
   pyenv and venv incantation every target here repeats. The
   `from dump_poll import open_table` import in `manage_emails.py` is left as
   is (optional tidy, not on the refactor list). Rejected: merging into one
   CLI (relocates code and puts the read-only command beside the destructive
   ones).
5. **Docs principle:** `POLLS.md` keeps what an operator needs and cannot read
   from the code or `make help`; numbers that live in code or config are
   pointed to, not restated. Changes: remove the command reference table
   (`make help` covers it) and the README's command block, leaving a link and
   one sentence; replace the definition-rules tables with a short list and a
   pointer to `docs/examples/all-question-types.json` (the lint's messages
   state each rule); rewrite monitoring around `make check-polls` with the
   trimmed log fields and the reasons table, replacing the long list of 400
   reasons with "any other 400"; cut "Cost and limits" to what is not in code
   (expected cost, why reserved concurrency is unset); fix statements the
   other tickets make false (at most two free-text questions, "a poll too big
   to submit fails here", access logs, saved queries, `hasEmail`,
   `hasBrowserToken`, `cloudfrontRequestId`). Keep how it fits together,
   one-time setup, add/change/close/roll back, the `jq` counting recipes and
   email management. Expected result: about 200 lines from 309. The links to
   the planning docs are left for the planning-doc ticket.

Consequences for other tickets:

- [Grill: test suite size and overlap](05-grill-test-suite-size.md): tests
  for `query_logs.py` (161 lines), the access-log queries (194) and the saved
  Logs Insights queries leave with their code; `test_dump_poll.py` (135) and
  `test_manage_emails.py` (304) stay; the new shell and jq have no tests
  unless the optional jq fixture test is wanted.
- The "Makefile and CI surface" fog item is resolved here and removed from the
  map's Not yet specified.
- New ticket
  [Grill: planning docs after the build](07-grill-planning-docs-after-build.md)
  graduates the planning-doc consolidation fog item.
