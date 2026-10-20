---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: observability layers

## Question

The branch has three overlapping ways to check on the polls, all unexercised
until real traffic exists:

- CloudFront access logs delivered to an S3 bucket, read through a Glue table,
  Athena workgroup and three saved queries (`stack/polls_access_log_queries.py`,
  the `_deliver_access_logs` method in `stack/polls.py`).
- Saved CloudWatch Logs Insights queries over the handler's JSON log lines
  (`SAVED_QUERIES` in `stack/polls.py`).
- `scripts/query_logs.py`, which runs the Athena queries from the command line.

Which to keep, trim, or drop, so the owner has the fewest moving parts that
still answer "is anything wrong with the polls?" Consider what each costs to
maintain (resources, golden-test lines, tests, docs) against the question it
answers that the others cannot.

Constraints: ADR 0001's architecture is fixed; the earlier decision to defer an
observability data model (map out-of-scope list) still stands.

## Resolution

Decided with the human. The CloudFront access-log layer goes entirely; the
handler-side layer stays, trimmed.

1. **Drop the CloudFront access-log layer.** The human only needs visibility
   into blocked or throttled traffic when it is caused by something fixable
   (WAF configuration) and accepts the blind spot otherwise. Removed:
   the S3 log bucket and its CloudFront delivery (source, destination,
   delivery, bucket policy), the Glue database and table, the Athena workgroup
   and saved queries, `stack/polls_access_log_queries.py` and its tests,
   `scripts/query_logs.py` and its tests, the `query-logs` Makefile target,
   the access-log section of `POLLS.md` and the README line.
2. **Blind spot covered by what already exists.** The shared WAF ACL and every
   rule on it already emit CloudWatch metrics and sampled requests
   (`stack/site.py`: `PollsSubmitRateLimit`, both managed rule sets, the ACL
   total), which shows a rule wrongly blocking people. Function-URL throttles
   (429 above the concurrency cap) never reach the handler; the Lambda
   `Throttles` and function URL metrics in CloudWatch show them. Accepted loss:
   a long-term, IP-level record of blocked and throttled traffic, and page
   views.
3. **Keep the handler log group** with 365-day retention and the structured
   JSON log lines (retention is required anyway; without it Lambda creates a
   group that never expires outside the template).
4. **Keep two saved Logs Insights queries:** `polls/errors` and
   `polls/rejections-by-reason`. Drop `polls/submissions-per-day` (results are
   read with `dump_poll.py`) and `polls/recent-requests` (a generic browse
   that can be written in the console when needed).

Consequences for other tickets:

- [Grill: stack layout and WAF rule ownership](04-grill-stack-layout.md):
  `_deliver_access_logs` and the access-log imports leave `stack/polls.py`
  (about 90 lines plus the 220-line module); the golden file shrinks by the
  bucket, delivery, Glue and Athena resources.
- [Grill: owner scripts and docs](06-grill-owner-scripts-and-docs.md):
  `query_logs.py` is gone, leaving `dump_poll.py` and `manage_emails.py`.
- [Grill: test suite size and overlap](05-grill-test-suite-size.md):
  `test_polls_access_log_queries.py` (194 lines) and `test_query_logs.py`
  (161 lines) are removed with their code.
- [Grill: submit handler structure](03-grill-handler-structure.md): the
  handler's log fields now serve two saved queries (`outcome`, `reason`,
  `level`, `status`, `errorType`, `errorCode`, `pollId`, `responseId`,
  `requestId`), which bounds what the log shaping has to emit. The
  `cloudfrontRequestId` field existed to correlate with access logs and
  has no consumer now.
- Supersedes the access-log parts of the earlier decision
  [Grill: observability and cost guardrails](../../wayfinder/poll-app/tickets/08-grill-observability-guardrails.md).

## Amendment

Decision 4 (keep two saved Logs Insights queries) was reversed by
[Grill: owner scripts and docs](06-grill-owner-scripts-and-docs.md): both
queries are dropped and the same two questions are answered by jq over a local
copy of the handler log (`make check-polls`, 90-day default). The log group,
its 365-day retention and the structured log lines in decision 3 stand; the
log group gets a pinned name.
