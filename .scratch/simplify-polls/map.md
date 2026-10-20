# Map: simplify the polls implementation on `research/poll-app`

## Destination

A **decision set**: for each area of the polls implementation (observability,
poll rules, handler, stack layout, tests, owner tooling and docs) a recorded
decision to keep, cut, or merge, with the maintenance rationale and a rough
size of the change. Done when someone can plan the refactor slices without
reopening these choices. Planning only: no refactoring happens in this effort.

## Notes

- Domain: the polls app in this repo; terms in root `CONTEXT.md`. The original
  decisions live in `.scratch/wayfinder/poll-app/map.md`.
- **Fixed:** [ADR 0001](../../docs/adr/0001-lambda-function-url-with-cloudfront-oac.md)
  (Lambda Function URL behind CloudFront OAC, DynamoDB, shared WAF ACL).
- Standing constraints: respondent-visible behaviour stays the same; `make static`
  keeps passing including a golden parameter test per stack and environment.
- Standing preference: fewer moving parts and one obvious place per change over
  flexibility nobody has asked for.
- The decisions are collected as a PRD in [spec.md](spec.md), the hand-off for
  planning the refactor slices. The slices are in [issues/](issues/), 01 to 14,
  in dependency order.
- Tracker: local markdown. Tickets live in `tickets/`; claim by setting
  `claimed:`, close by setting `status: closed` and adding a `## Resolution`.

## Decisions so far

<!-- one line per closed ticket: [title](tickets/file.md) — gist -->

- [Grill: observability layers](tickets/01-grill-observability-layers.md) — drop the whole CloudFront access-log layer (S3 bucket, delivery, Glue, Athena, `query_logs.py`) and accept the blind spot, relying on existing WAF metrics and Lambda metrics; keep the 365-day handler log group and two saved Logs Insights queries (`errors`, `rejections-by-reason`; the saved queries were later dropped, see the owner-scripts decision)
- [Grill: poll definition rules and shared limits](tickets/02-grill-poll-definition-rules.md) — keep the structural poll-file lint and drop the body-budget check (`worst_case_body_bytes`, `RESERVED_BODY_BYTES`, its tests); keep the `MAX_TEXT_CHARS` contract test and the symlink bundle as they are
- [Grill: submit handler structure](tickets/03-grill-handler-structure.md) — trim the log line to `level`, `outcome`, `status`, `reason`, `pollId`, `responseId`, `bodyBytes`, `requestId`, `errorType`, `errorCode`; leave the `facts`/`_Services` wiring; replace the Crockford response ID with a timestamp-plus-random one (clear stored test data first); keep `handler.py` as one file
- [Grill: stack layout and WAF rule ownership](tickets/04-grill-stack-layout.md) — keep the polls rate rule on the shared ACL in Site (a separate ACL is about $5-7 a month more); one hostname method on `PollsSetting` for both inputs; keep `PollsStack` as one stack (no constructs: logical-ID replacement risk, no test benefit) and inline the two remaining saved queries (moot after the owner-scripts decision)
- [Grill: owner scripts and docs](tickets/06-grill-owner-scripts-and-docs.md) — check problems by downloading the handler log and CloudWatch metrics to a gitignored `.polls-check/` and searching with stored jq files (`make fetch-logs`, `fetch-metrics`, `check-polls`, 90-day default, no Python); pin the log group name; drop the two saved queries; keep `dump_poll.py` and `manage_emails.py` and their targets; trim `POLLS.md` and the README to what code and `make help` cannot say
- [Grill: test suite size and overlap](tickets/05-grill-test-suite-size.md) — delete the launch-poll content test (it breaks the build when a second poll is added) and merge the duplicate bundled-poll submission tests; keep infra tests beyond the golden only for silent-erasure invariants, what the golden cannot see, and settings logic; pin each handler log behaviour once; keep `test_handler.py` as one file; leave the JS, script and page-shell tests; about 850 of 3,950 test lines go
- [Grill: planning docs after the build](tickets/07-grill-planning-docs-after-build.md) — keep the spec and the two research notes ADR 0001 cites, moved to `docs/polls/` with a "Changes since this spec" note; delete the rest of `.scratch/wayfinder/poll-app/` after launch verification (updating issue 15 and the build plan first, tagging the branch tip before deleting) and `.scratch/simplify-polls/` once the refactors ship; no change to `CONTEXT.md`, ADR 0001 or `CLAUDE.md`, one line in `issue-tracker.md`

## Frontier (open, unblocked)

(none)

## Blocked

(none)

## Not yet specified

(none: the way to the destination is clear)

## Out of scope

- Changing ADR 0001's architecture (compute, storage, routing).
- Performing any of the refactors; this map ends at the decisions.
- **Refactor ordering and slicing:** which slice goes first and how the decisions split into issues. Ruled out of scope because the destination is the decision set itself; it is hand-off material for a PRD or issue breakdown made from the Decisions so far.
- Respondent-visible behaviour changes.
- The observability data model (filtering and normalising events), already ruled out of the original poll-app map.
